# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from fastapi_lifespan_manager import LifespanManager
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.fastapi.long_running_tasks._manager import FastAPILongRunningManager
from servicelib.fastapi.long_running_tasks.client import configure_client
from servicelib.fastapi.long_running_tasks.server import (
    configure_server,
    get_long_running_manager,
)
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.models import TaskId, TaskProgress, TaskStatus
from servicelib.long_running_tasks.task import TaskRegistry
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def _echo_task(progress: TaskProgress, value: str) -> str:
    return value


TaskRegistry.register(_echo_task)


@pytest.fixture
def server_routes() -> APIRouter:
    routes = APIRouter()

    @routes.post("/echo-task", response_model=TaskId, status_code=status.HTTP_202_ACCEPTED)
    async def create_echo_task(
        value: str,
        long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
    ) -> TaskId:
        return await lrt_api.start_task(
            long_running_manager.rpc_client,
            long_running_manager.lrt_namespace,
            _echo_task.__name__,
            value=value,
        )

    return routes


@pytest.fixture
async def app(
    server_routes: APIRouter,
    use_in_memory_redis: RedisSettings,
    rabbit_service: RabbitSettings,
) -> AsyncIterator[FastAPI]:
    app_lifespan: LifespanManager = LifespanManager()
    _app = FastAPI(title="test app (lifespan)", lifespan=app_lifespan)
    _app.include_router(server_routes)

    configure_server(
        _app,
        app_lifespan,
        redis_settings=use_in_memory_redis,
        rabbit_settings=rabbit_service,
        lrt_namespace="test-lifespan",
    )
    configure_client(app_lifespan)

    async with ASGILifespanManager(_app, startup_timeout=30, shutdown_timeout=30):
        yield _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_configure_client_sets_app_state(app: FastAPI) -> None:
    assert app.state.long_running_client_configuration is not None


async def test_configure_server_sets_app_state(app: FastAPI) -> None:
    assert isinstance(app.state.long_running_manager, FastAPILongRunningManager)


async def test_workflow(app: FastAPI, client: AsyncClient) -> None:
    create_url = app.url_path_for("create_echo_task")
    response = await client.post(f"{create_url}", params={"value": "hello"})
    assert response.status_code == status.HTTP_202_ACCEPTED
    task_id = TypeAdapter(TaskId).validate_python(response.json())

    status_url = app.url_path_for("get_task_status", task_id=task_id)
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(30),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(f"{status_url}")
            assert result.status_code == status.HTTP_200_OK
            task_status = TaskStatus.model_validate(result.json())
            assert task_status.done

    result_url = app.url_path_for("get_task_result", task_id=task_id)
    result = await client.get(f"{result_url}")
    assert result.status_code == status.HTTP_200_OK
    assert result.json() == "hello"


async def test_teardown_called_once_on_shutdown(
    mocker: MockerFixture,
    server_routes: APIRouter,
    use_in_memory_redis: RedisSettings,
    rabbit_service: RabbitSettings,
) -> None:
    teardown_spy = mocker.spy(FastAPILongRunningManager, "teardown")

    app_lifespan: LifespanManager = LifespanManager()
    _app = FastAPI(lifespan=app_lifespan)
    _app.include_router(server_routes)
    configure_server(
        _app,
        app_lifespan,
        redis_settings=use_in_memory_redis,
        rabbit_settings=rabbit_service,
        lrt_namespace="test-lifespan-teardown",
    )
    configure_client(app_lifespan)

    async with ASGILifespanManager(_app, startup_timeout=30, shutdown_timeout=30):
        teardown_spy.assert_not_called()

    teardown_spy.assert_called_once()
