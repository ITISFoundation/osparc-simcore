# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from typing import AsyncIterable, Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, status
from httpx import AsyncClient
from pydantic import AnyHttpUrl, PositiveFloat, TypeAdapter
from servicelib.fastapi.long_running_tasks._context_manager import _ProgressManager
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressMessage,
    ProgressPercent,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as setup_client
from servicelib.fastapi.long_running_tasks.server import (
    TaskId,
    TaskProgress,
    TasksManager,
    get_tasks_manager,
)
from servicelib.fastapi.long_running_tasks.server import setup as setup_server
from servicelib.fastapi.long_running_tasks.server import start_task
from servicelib.long_running_tasks._errors import (
    TaskClientResultError,
    TaskClientTimeoutError,
)

TASK_SLEEP_INTERVAL: Final[PositiveFloat] = 0.1

# UTILS


async def _assert_task_removed(
    async_client: AsyncClient, task_id: TaskId, router_prefix: str
) -> None:
    result = await async_client.get(f"{router_prefix}/tasks/{task_id}")
    assert result.status_code == status.HTTP_404_NOT_FOUND


async def a_test_task(task_progress: TaskProgress) -> int:
    await asyncio.sleep(TASK_SLEEP_INTERVAL)
    return 42


async def a_failing_test_task(task_progress: TaskProgress) -> None:
    await asyncio.sleep(TASK_SLEEP_INTERVAL)
    msg = "I am failing as requested"
    raise RuntimeError(msg)


@pytest.fixture
def user_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/success", status_code=status.HTTP_200_OK)
    async def create_task_user_defined_route(
        tasks_manager: TasksManager = Depends(get_tasks_manager),
    ) -> TaskId:
        task_id = start_task(tasks_manager, task=a_test_task)
        return task_id

    @router.get("/api/failing", status_code=status.HTTP_200_OK)
    async def create_task_which_fails(
        task_manager: TasksManager = Depends(get_tasks_manager),
    ) -> TaskId:
        task_id = start_task(task_manager, task=a_failing_test_task)
        return task_id

    return router


@pytest.fixture
async def bg_task_app(
    user_routes: APIRouter, router_prefix: str
) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    app.include_router(user_routes)

    setup_server(app, router_prefix=router_prefix)
    setup_client(app, router_prefix=router_prefix)

    async with LifespanManager(app):
        yield app


@pytest.fixture
def mock_task_id() -> TaskId:
    return TypeAdapter(TaskId).validate_python("fake_task_id")


async def test_task_result(
    bg_task_app: FastAPI, async_client: AsyncClient, router_prefix: str
) -> None:
    result = await async_client.get("/api/success")
    assert result.status_code == status.HTTP_200_OK, result.text
    task_id = result.json()

    url = TypeAdapter(AnyHttpUrl).validate_python("http://backgroud.testserver.io/")
    client = Client(app=bg_task_app, async_client=async_client, base_url=url)
    async with periodic_task_result(
        client,
        task_id,
        task_timeout=10,
        status_poll_interval=TASK_SLEEP_INTERVAL / 3,
    ) as result:
        assert result == 42

    await _assert_task_removed(async_client, task_id, router_prefix)


async def test_task_result_times_out(
    bg_task_app: FastAPI, async_client: AsyncClient, router_prefix: str
) -> None:
    result = await async_client.get("/api/success")
    assert result.status_code == status.HTTP_200_OK, result.text
    task_id = result.json()

    url = TypeAdapter(AnyHttpUrl).validate_python("http://backgroud.testserver.io/")
    client = Client(app=bg_task_app, async_client=async_client, base_url=url)
    timeout = TASK_SLEEP_INTERVAL / 10
    with pytest.raises(TaskClientTimeoutError) as exec_info:
        async with periodic_task_result(
            client,
            task_id,
            task_timeout=timeout,
            status_poll_interval=TASK_SLEEP_INTERVAL / 3,
        ):
            pass
    assert (
        f"{exec_info.value}"
        == f"Timed out after {timeout} seconds while awaiting '{task_id}' to complete"
    )

    await _assert_task_removed(async_client, task_id, router_prefix)


async def test_task_result_task_result_is_an_error(
    bg_task_app: FastAPI, async_client: AsyncClient, router_prefix: str
) -> None:
    result = await async_client.get("/api/failing")
    assert result.status_code == status.HTTP_200_OK, result.text
    task_id = result.json()

    url = TypeAdapter(AnyHttpUrl).validate_python("http://backgroud.testserver.io/")
    client = Client(app=bg_task_app, async_client=async_client, base_url=url)
    with pytest.raises(TaskClientResultError) as exec_info:
        async with periodic_task_result(
            client,
            task_id,
            task_timeout=10,
            status_poll_interval=TASK_SLEEP_INTERVAL / 3,
        ):
            pass
    assert f"{exec_info.value}".startswith(f"Task {task_id} finished with exception:")
    assert "I am failing as requested" in f"{exec_info.value}"
    await _assert_task_removed(async_client, task_id, router_prefix)


@pytest.mark.parametrize("repeat", [1, 2, 10])
async def test_progress_updater(repeat: int, mock_task_id: TaskId) -> None:
    counter = 0
    received = ()

    async def progress_update(
        message: ProgressMessage, percent: ProgressPercent | None, task_id: TaskId
    ) -> None:
        nonlocal counter
        nonlocal received
        counter += 1
        received = (message, percent)
        assert task_id == mock_task_id

    progress_updater = _ProgressManager(progress_update)

    # different from None and the last value only
    # triggers once
    for _ in range(repeat):
        await progress_updater.update(mock_task_id, message="")
        assert counter == 1
        assert received == ("", None)

    for _ in range(repeat):
        await progress_updater.update(
            mock_task_id, percent=TypeAdapter(ProgressPercent).validate_python(0.0)
        )
        assert counter == 2
        assert received == ("", 0.0)

    for _ in range(repeat):
        await progress_updater.update(
            mock_task_id,
            percent=TypeAdapter(ProgressPercent).validate_python(1.0),
            message="done",
        )
        assert counter == 3
        assert received == ("done", 1.0)

    # setting percent or message to None
    # will not trigger an event

    for _ in range(repeat):
        await progress_updater.update(mock_task_id, message=None)
        assert counter == 3
        assert received == ("done", 1.0)

    for _ in range(repeat):
        await progress_updater.update(mock_task_id, percent=None)
        assert counter == 3
        assert received == ("done", 1.0)

    for _ in range(repeat):
        await progress_updater.update(mock_task_id, percent=None, message=None)
        assert counter == 3
        assert received == ("done", 1.0)

    for _ in range(repeat):
        await progress_updater.update(mock_task_id)
        assert counter == 3
        assert received == ("done", 1.0)
