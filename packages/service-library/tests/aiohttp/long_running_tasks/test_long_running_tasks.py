# pylint: disable=redefined-outer-name

"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""


import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import long_running_tasks, status
from servicelib.aiohttp.long_running_tasks.server import TaskGet, TaskId
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares
from servicelib.long_running_tasks._task import TaskContext
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture
def app(server_routes: web.RouteTableDef) -> web.Application:
    app = web.Application()
    app.add_routes(server_routes)
    # this adds enveloping and error middlewares
    append_rest_middlewares(app, api_version="")
    long_running_tasks.server.setup(app, router_prefix="/futures")

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


async def test_workflow(
    client: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
):
    assert client.app
    task_id = await start_long_running_task(client)

    # get progress updates
    progress_updates = []
    status_url = client.app.router["get_task_status"].url_for(task_id=task_id)
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
            progress_updates.append(
                (task_status.task_progress.message, task_status.task_progress.percent)
            )
            print(f"<-- received task status: {task_status.model_dump_json(indent=2)}")
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
    result_url = client.app.router["get_task_result"].url_for(task_id=task_id)
    result = await client.get(f"{result_url}")
    task_result, error = await assert_status(result, status.HTTP_201_CREATED)
    assert task_result
    assert not error
    assert task_result == [f"{x}" for x in range(10)]
    # getting the result again should raise a 404
    result = await client.get(f"{result_url}")
    await assert_status(result, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize(
    "method, route_name",
    [
        ("GET", "get_task_status"),
        ("GET", "get_task_result"),
        ("DELETE", "cancel_and_delete_task"),
    ],
)
async def test_get_task_wrong_task_id_raises_not_found(
    client: TestClient, method: str, route_name: str
):
    assert client.app
    url = client.app.router[route_name].url_for(task_id="fake_task_id")
    result = await client.request(method, f"{url}")
    await assert_status(result, status.HTTP_404_NOT_FOUND)


async def test_failing_task_returns_error(
    client: TestClient,
    start_long_running_task: Callable[[TestClient, Any], Awaitable[TaskId]],
    wait_for_task: Callable[[TestClient, TaskId, TaskContext], Awaitable[None]],
):
    assert client.app
    task_id = await start_long_running_task(client, fail=f"{True}")
    # wait for it to finish
    await wait_for_task(client, task_id, {})
    # get the result
    result_url = client.app.router["get_task_result"].url_for(task_id=task_id)
    result = await client.get(f"{result_url}")
    data, error = await assert_status(result, status.HTTP_500_INTERNAL_SERVER_ERROR)
    assert not data
    assert error
    assert "errors" in error
    assert len(error["errors"]) == 1
    assert error["errors"][0]["code"] == "RuntimeError"
    assert error["errors"][0]["message"] == "We were asked to fail!!"


async def test_get_results_before_tasks_finishes_returns_404(
    client: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
):
    assert client.app
    task_id = await start_long_running_task(client)

    result_url = client.app.router["get_task_result"].url_for(task_id=task_id)
    result = await client.get(f"{result_url}")
    await assert_status(result, status.HTTP_404_NOT_FOUND)


async def test_cancel_task(
    client: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
):
    assert client.app
    task_id = await start_long_running_task(client)

    # cancel the task
    delete_url = client.app.router["cancel_and_delete_task"].url_for(task_id=task_id)
    result = await client.delete(f"{delete_url}")
    data, error = await assert_status(result, status.HTTP_204_NO_CONTENT)
    assert not data
    assert not error

    # it should be gone, so no status
    status_url = client.app.router["get_task_status"].url_for(task_id=task_id)
    result = await client.get(f"{status_url}")
    await assert_status(result, status.HTTP_404_NOT_FOUND)
    # and also no results
    result_url = client.app.router["get_task_result"].url_for(task_id=task_id)
    result = await client.get(f"{result_url}")
    await assert_status(result, status.HTTP_404_NOT_FOUND)

    # try cancelling again
    result = await client.delete(f"{delete_url}")
    await assert_status(result, status.HTTP_404_NOT_FOUND)


async def test_list_tasks_empty_list(client: TestClient):
    # initially empty
    assert client.app
    list_url = client.app.router["list_tasks"].url_for()
    result = await client.get(f"{list_url}")
    data, error = await assert_status(result, status.HTTP_200_OK)
    assert not error
    assert data == []


async def test_list_tasks(
    client: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
    wait_for_task: Callable[[TestClient, TaskId, TaskContext], Awaitable[None]],
):
    assert client.app
    # now start a few tasks
    NUM_TASKS = 10
    results = await asyncio.gather(
        *(start_long_running_task(client) for _ in range(NUM_TASKS))
    )

    # check we have the full list
    list_url = client.app.router["list_tasks"].url_for()
    result = await client.get(f"{list_url}")
    data, error = await assert_status(result, status.HTTP_200_OK)
    assert not error
    list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(data)
    assert len(list_of_tasks) == NUM_TASKS

    # the task name is properly formatted
    assert all(
        task.task_name == "POST /long_running_task:start?num_strings=10&sleep_time=0.2"
        for task in list_of_tasks
    )
    # now wait for them to finish
    await asyncio.gather(*(wait_for_task(client, task_id, {}) for task_id in results))
    # now get the result one by one

    for task_index, task_id in enumerate(results):
        result_url = client.app.router["get_task_result"].url_for(task_id=task_id)
        await client.get(f"{result_url}")
        # the list shall go down one by one
        result = await client.get(f"{list_url}")
        data, error = await assert_status(result, status.HTTP_200_OK)
        assert not error
        list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(data)
        assert len(list_of_tasks) == NUM_TASKS - (task_index + 1)
