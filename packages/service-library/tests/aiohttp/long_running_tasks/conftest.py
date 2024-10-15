# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pydantic import BaseModel, TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import long_running_tasks, status
from servicelib.aiohttp.long_running_tasks.server import TaskId
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.long_running_tasks._task import TaskContext
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


async def _string_list_task(
    task_progress: long_running_tasks.server.TaskProgress,
    num_strings: int,
    sleep_time: float,
    fail: bool,
) -> web.Response:
    generated_strings = []
    for index in range(num_strings):
        generated_strings.append(f"{index}")
        await asyncio.sleep(sleep_time)
        task_progress.update(message="generated item", percent=index / num_strings)
        if fail:
            msg = "We were asked to fail!!"
            raise RuntimeError(msg)

    # NOTE: this code is used just for the sake of not returning the default 200
    return web.json_response(
        data={"data": generated_strings}, status=status.HTTP_201_CREATED
    )


@pytest.fixture
def task_context(faker: Faker) -> TaskContext:
    return {"user_id": faker.pyint(), "product": faker.pystr()}


@pytest.fixture
def long_running_task_entrypoint() -> str:
    return "long_running_entrypoint"


@pytest.fixture
def server_routes(
    task_context: TaskContext, long_running_task_entrypoint: str
) -> web.RouteTableDef:
    routes = web.RouteTableDef()

    class _LongTaskQueryParams(BaseModel):
        num_strings: int
        sleep_time: float
        fail: bool = False

    @routes.post("/long_running_task:start", name=long_running_task_entrypoint)
    async def generate_list_strings(request: web.Request) -> web.Response:
        query_params = parse_request_query_parameters_as(_LongTaskQueryParams, request)
        return await long_running_tasks.server.start_long_running_task(
            request,
            _string_list_task,
            num_strings=query_params.num_strings,
            sleep_time=query_params.sleep_time,
            fail=query_params.fail,
            task_context=task_context,
        )

    return routes


@pytest.fixture
def start_long_running_task(
    long_running_task_entrypoint,
) -> Callable[[TestClient], Awaitable[TaskId]]:
    async def _caller(client: TestClient, **query_kwargs) -> TaskId:
        assert client.app
        url = (
            client.app.router[long_running_task_entrypoint]
            .url_for()
            .update_query(num_strings=10, sleep_time=f"{0.2}", **query_kwargs)
        )
        resp = await client.post(f"{url}")
        data, error = await assert_status(resp, status.HTTP_202_ACCEPTED)
        assert data
        assert not error
        task_get = TypeAdapter(long_running_tasks.server.TaskGet).validate_python(data)
        return task_get.task_id

    return _caller


@pytest.fixture
def wait_for_task() -> Callable[[TestClient, TaskId, TaskContext], Awaitable[None]]:
    async def _waiter(
        client: TestClient,
        task_id: TaskId,
        task_context: TaskContext,
    ) -> None:
        assert client.app
        status_url = (
            client.app.router["get_task_status"]
            .url_for(task_id=task_id)
            .with_query(task_context)
        )
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(60),
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                result = await client.get(f"{status_url}")
                data, error = await assert_status(result, status.HTTP_200_OK)
                assert data
                assert not error
                task_status = long_running_tasks.server.TaskStatus.model_validate(data)
                assert task_status
                assert task_status.done

    return _waiter
