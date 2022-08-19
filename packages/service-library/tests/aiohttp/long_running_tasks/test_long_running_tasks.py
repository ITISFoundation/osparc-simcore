# pylint: disable=redefined-outer-name

"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""


import asyncio
import json
from typing import Callable, Final

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import BaseModel, parse_obj_as

# TESTS
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import long_running_tasks
from servicelib.aiohttp.long_running_tasks.server import TaskGet, TaskId
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares
from servicelib.json_serialization import json_dumps
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

TASKS_ROUTER_PREFIX: Final[str] = "/futures"
LONG_RUNNING_TASK_ENTRYPOINT: Final[str] = "long_running_task"


async def _wait_for_task_to_finish(client: TestClient, task_id: TaskId):
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}")
            data, error = await assert_status(result, web.HTTPOk)
            assert data
            assert not error
            task_status = long_running_tasks.server.TaskStatus.parse_obj(data)
            assert task_status
            assert task_status.done


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
        task_progress.publish(message="generated item", percent=index / num_strings)
        if fail:
            raise RuntimeError("We were asked to fail!!")

    # NOTE: this code is used just for the sake of not returning the default 200
    return web.json_response(
        data={"data": generated_strings}, status=web.HTTPCreated.status_code
    )


@pytest.fixture
def server_routes() -> web.RouteTableDef:
    routes = web.RouteTableDef()

    class _LongTaskQueryParams(BaseModel):
        num_strings: int
        sleep_time: float
        fail: bool = False

    @routes.post("/long_running_task:start", name=LONG_RUNNING_TASK_ENTRYPOINT)
    async def generate_list_strings(request: web.Request):
        task_manager = long_running_tasks.server.get_tasks_manager(request.app)
        query_params = parse_request_query_parameters_as(_LongTaskQueryParams, request)
        assert task_manager, "task manager is not initiated!"

        task_id = long_running_tasks.server.start_task(
            task_manager,
            _string_list_task,
            handler_context={
                "user_id": 123,
            },
            num_strings=query_params.num_strings,
            sleep_time=query_params.sleep_time,
            fail=query_params.fail,
        )
        return web.json_response(
            data={"data": task_id},
            status=web.HTTPAccepted.status_code,
            dumps=json_dumps,
        )

    return routes


@pytest.fixture
def app(server_routes: web.RouteTableDef) -> web.Application:
    app = web.Application()
    app.add_routes(server_routes)
    # this adds enveloping and error middlewares
    append_rest_middlewares(app, api_version="")
    long_running_tasks.server.setup(app, router_prefix=TASKS_ROUTER_PREFIX)

    return app


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    app: web.Application,
) -> TestClient:

    return event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": unused_tcp_port_factory()})
    )


async def test_workflow(client: TestClient):
    assert client.app
    url = (
        client.app.router[LONG_RUNNING_TASK_ENTRYPOINT]
        .url_for()
        .update_query(num_strings=10, sleep_time=0.2)
    )

    result = await client.post(f"{url}")
    data, error = await assert_status(result, web.HTTPAccepted)
    assert data
    assert not error
    task_id = parse_obj_as(long_running_tasks.server.TaskId, data)

    # get progress updates
    progress_updates = []
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}")
            data, error = await assert_status(result, web.HTTPOk)
            assert data
            assert not error
            task_status = long_running_tasks.server.TaskStatus.parse_obj(data)
            assert task_status
            progress_updates.append(
                (task_status.task_progress.message, task_status.task_progress.percent)
            )
            print(f"<-- received task status: {task_status.json(indent=2)}")
            assert task_status.done, "task incomplete"
            print(
                f"-- waiting for task status completed successfully: {json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
            )
    EXPECTED_MESSAGES = [
        ("starting", 0.0),
        ("generated item", 0.0),
        ("generated item", 0.1),
        ("generated item", 0.2),
        ("generated item", 0.3),
        ("generated item", 0.4),
        ("generated item", 0.5),
        ("generated item", 0.6),
        ("generated item", 0.7),
        ("generated item", 0.8),
        ("finished", 1.0),
    ]
    assert all(x in progress_updates for x in EXPECTED_MESSAGES)
    # now get the result
    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}/result")
    task_result, error = await assert_status(result, web.HTTPCreated)
    assert task_result
    assert not error
    assert task_result == [f"{x}" for x in range(10)]
    # getting the result again should raise a 404
    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}/result")
    await assert_status(result, web.HTTPNotFound)


async def test_failing_task_returns_error(client: TestClient):
    assert client.app
    url = (
        client.app.router[LONG_RUNNING_TASK_ENTRYPOINT]
        .url_for()
        .update_query(num_strings=12, sleep_time=0.1, fail="true")
    )
    result = await client.post(f"{url}")
    data, error = await assert_status(result, web.HTTPAccepted)
    assert data
    assert not error
    task_id = parse_obj_as(long_running_tasks.server.TaskId, data)
    # wait for it to finish
    await _wait_for_task_to_finish(client, task_id)
    # get the result
    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}/result")
    data, error = await assert_status(result, web.HTTPInternalServerError)
    assert not data
    assert error
    assert "errors" in error
    assert len(error["errors"]) == 1
    assert error["errors"][0]["code"] == "RuntimeError"
    assert error["errors"][0]["message"] == "We were asked to fail!!"


async def test_get_results_before_tasks_finishes_returns_404(client: TestClient):
    assert client.app
    url = (
        client.app.router[LONG_RUNNING_TASK_ENTRYPOINT]
        .url_for()
        .update_query(num_strings=10, sleep_time=0.2)
    )
    result = await client.post(f"{url}")
    data, error = await assert_status(result, web.HTTPAccepted)
    assert data
    assert not error
    task_id = parse_obj_as(long_running_tasks.server.TaskId, data)

    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}/result")
    await assert_status(result, web.HTTPNotFound)


async def test_cancel_workflow(client: TestClient):
    assert client.app
    url = (
        client.app.router[LONG_RUNNING_TASK_ENTRYPOINT]
        .url_for()
        .update_query(num_strings=10, sleep_time=0.2)
    )
    result = await client.post(f"{url}")
    data, error = await assert_status(result, web.HTTPAccepted)
    assert data
    assert not error
    task_id = parse_obj_as(long_running_tasks.server.TaskId, data)

    # cancel the task
    result = await client.delete(f"{TASKS_ROUTER_PREFIX}/{task_id}")
    data, error = await assert_status(result, web.HTTPNoContent)
    assert not data
    assert not error

    # it should be gone, so no status
    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}")
    await assert_status(result, web.HTTPNotFound)
    # and also no results
    result = await client.get(f"{TASKS_ROUTER_PREFIX}/{task_id}/result")
    await assert_status(result, web.HTTPNotFound)

    # try cancelling again
    result = await client.delete(f"{TASKS_ROUTER_PREFIX}/{task_id}")
    await assert_status(result, web.HTTPNotFound)


async def test_list_tasks_empty_list(client: TestClient):
    # initially empty
    list_url = URL(f"{TASKS_ROUTER_PREFIX}")
    result = await client.get(f"{list_url}")
    data, error = await assert_status(result, web.HTTPOk)
    assert not error
    assert data == []


async def test_list_tasks(client: TestClient):
    assert client.app
    url = (
        client.app.router[LONG_RUNNING_TASK_ENTRYPOINT]
        .url_for()
        .update_query(num_strings=10, sleep_time=0.2)
    )

    # now start a few tasks
    NUM_TASKS = 10
    results = await asyncio.gather(*(client.post(f"{url}") for _ in range(NUM_TASKS)))
    results = await asyncio.gather(
        *(assert_status(result, web.HTTPAccepted) for result in results)
    )

    # check we have the full list
    list_url = URL(f"{TASKS_ROUTER_PREFIX}")
    result = await client.get(f"{list_url}")
    data, error = await assert_status(result, web.HTTPOk)
    assert not error
    list_of_tasks = parse_obj_as(list[TaskGet], data)
    assert len(list_of_tasks) == NUM_TASKS

    # now wait for them to finish
    await asyncio.gather(
        *(_wait_for_task_to_finish(client, data) for data, error in results)
    )
