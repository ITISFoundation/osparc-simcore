# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import urllib.parse
from typing import Awaitable, Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pydantic import BaseModel, parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import long_running_tasks
from servicelib.aiohttp.long_running_tasks.server import (
    TaskId,
    create_task_name_from_request,
)
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.json_serialization import json_dumps
from servicelib.long_running_tasks._task import TaskContext
from tenacity._asyncio import AsyncRetrying
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
            raise RuntimeError("We were asked to fail!!")

    # NOTE: this code is used just for the sake of not returning the default 200
    return web.json_response(
        data={"data": generated_strings}, status=web.HTTPCreated.status_code
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
    async def generate_list_strings(request: web.Request):
        task_manager = long_running_tasks.server.get_tasks_manager(request.app)
        query_params = parse_request_query_parameters_as(_LongTaskQueryParams, request)
        assert task_manager, "task manager is not initiated!"
        task_name = create_task_name_from_request(request)
        task_id = long_running_tasks.server.start_task(
            task_manager,
            _string_list_task,
            num_strings=query_params.num_strings,
            sleep_time=query_params.sleep_time,
            fail=query_params.fail,
            task_context=task_context,
            task_name=task_name,
        )
        assert task_id
        assert task_id.startswith(urllib.parse.quote(task_name, safe=""))
        return web.json_response(
            data={"data": task_id},
            status=web.HTTPAccepted.status_code,
            dumps=json_dumps,
        )

    return routes


@pytest.fixture
def start_task(
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
        data, error = await assert_status(resp, web.HTTPAccepted)
        assert data
        assert not error
        task_id = parse_obj_as(long_running_tasks.server.TaskId, data)
        return task_id

    return _caller


@pytest.fixture
def task_waiter() -> Callable[[TestClient, TaskId, TaskContext], Awaitable[None]]:
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
                data, error = await assert_status(result, web.HTTPOk)
                assert data
                assert not error
                task_status = long_running_tasks.server.TaskStatus.parse_obj(data)
                assert task_status
                assert task_status.done

    return _waiter
