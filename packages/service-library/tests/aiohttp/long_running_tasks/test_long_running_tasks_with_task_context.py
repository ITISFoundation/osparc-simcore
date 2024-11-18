# pylint: disable=redefined-outer-name

"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a AIOHTTP server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""


import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Optional

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import TypeAdapter, create_model
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import long_running_tasks, status
from servicelib.aiohttp.long_running_tasks._server import (
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from servicelib.aiohttp.long_running_tasks.server import TaskGet, TaskId
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares
from servicelib.aiohttp.typing_extension import Handler
from servicelib.long_running_tasks._task import TaskContext

# WITH TASK CONTEXT
# NOTE: as the long running task framework may be used in any number of services
# in some cases there might be specific so-called task contexts.
# For instance in the webserver the tasks are linked to a specific user_id and product
# that is retrieved through some complex method
# all the subsequent routes to GET tasks or GET tasks/{task_id}, ... must only be
# retrieved if they satisfy to this context (i.e. only user_id=3 can see the tasks of user_id=3)


@pytest.fixture
def task_context_decorator(task_context: TaskContext):
    query_model = create_model(
        "_TaskContextQueryParam",
        **{k: (Optional[type(v).__name__], None) for k, v in task_context.items()},
    )

    def _pass_user_id_decorator(handler: Handler):
        @wraps(handler)
        async def _test_task_context_decorator(
            request: web.Request,
        ) -> web.StreamResponse:
            """this task context callback tries to get the user_id from the query if available"""
            query_param = parse_request_query_parameters_as(query_model, request)
            request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY] = query_param.model_dump()
            return await handler(request)

        return _test_task_context_decorator

    return _pass_user_id_decorator


@pytest.fixture
def app_with_task_context(
    server_routes: web.RouteTableDef, task_context_decorator
) -> web.Application:
    app = web.Application()
    app.add_routes(server_routes)
    # this adds enveloping and error middlewares
    append_rest_middlewares(app, api_version="")
    long_running_tasks.server.setup(
        app,
        router_prefix="/futures_with_task_context",
        task_request_context_decorator=task_context_decorator,
    )

    return app


@pytest.fixture
def client_with_task_context(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    app_with_task_context: web.Application,
) -> TestClient:

    return event_loop.run_until_complete(
        aiohttp_client(
            app_with_task_context, server_kwargs={"port": unused_tcp_port_factory()}
        )
    )


async def test_list_tasks(
    client_with_task_context: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
    task_context: TaskContext,
):
    assert client_with_task_context.app

    # start one task
    await start_long_running_task(client_with_task_context)

    # the list should be empty if we do not pass the expected context
    list_url = client_with_task_context.app.router["list_tasks"].url_for()
    result = await client_with_task_context.get(f"{list_url}")
    data, error = await assert_status(result, status.HTTP_200_OK)
    assert not error
    list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(data)
    assert len(list_of_tasks) == 0

    # the list should be full if we pass the expected context
    result = await client_with_task_context.get(
        f"{list_url.update_query(task_context)}"
    )
    data, error = await assert_status(result, status.HTTP_200_OK)
    assert not error
    list_of_tasks = TypeAdapter(list[TaskGet]).validate_python(data)
    assert len(list_of_tasks) == 1


async def test_get_task_status(
    client_with_task_context: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
    task_context: TaskContext,
):
    assert client_with_task_context.app

    task_id = await start_long_running_task(client_with_task_context)
    # calling without Task context should find nothing
    status_url = client_with_task_context.app.router["get_task_status"].url_for(
        task_id=task_id
    )
    resp = await client_with_task_context.get(f"{status_url}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)
    # calling with context should find the task
    resp = await client_with_task_context.get(f"{status_url.with_query(task_context)}")
    await assert_status(resp, status.HTTP_200_OK)


async def test_get_task_result(
    client_with_task_context: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
    task_context: TaskContext,
    wait_for_task: Callable[[TestClient, TaskId, TaskContext], Awaitable[None]],
):
    assert client_with_task_context.app
    task_id = await start_long_running_task(client_with_task_context)
    await wait_for_task(client_with_task_context, task_id, task_context)
    # calling without Task context should find nothing
    result_url = client_with_task_context.app.router["get_task_result"].url_for(
        task_id=task_id
    )
    resp = await client_with_task_context.get(f"{result_url}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)
    # calling with context should find the task
    resp = await client_with_task_context.get(f"{result_url.with_query(task_context)}")
    await assert_status(resp, status.HTTP_201_CREATED)


async def test_cancel_task(
    client_with_task_context: TestClient,
    start_long_running_task: Callable[[TestClient], Awaitable[TaskId]],
    task_context: TaskContext,
):
    assert client_with_task_context.app
    task_id = await start_long_running_task(client_with_task_context)
    cancel_url = client_with_task_context.app.router["cancel_and_delete_task"].url_for(
        task_id=task_id
    )
    # calling cancel without task context should find nothing
    resp = await client_with_task_context.delete(f"{cancel_url}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)
    # calling with context should find and delete the task
    resp = await client_with_task_context.delete(
        f"{cancel_url.update_query(task_context)}"
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
    # calling with context a second time should find nothing
    resp = await client_with_task_context.delete(
        f"{cancel_url.update_query(task_context)}"
    )
    await assert_status(resp, status.HTTP_404_NOT_FOUND)
