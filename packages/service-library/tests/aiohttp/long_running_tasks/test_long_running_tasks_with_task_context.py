# pylint: disable=redefined-outer-name

"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""


import asyncio
from functools import wraps
from typing import Any, Callable, Final, Optional

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import BaseModel, parse_obj_as

# TESTS
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import long_running_tasks
from servicelib.aiohttp.long_running_tasks._server import (
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from servicelib.aiohttp.long_running_tasks.server import TaskGet, TaskId
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares
from servicelib.aiohttp.typing_extension import Handler
from servicelib.json_serialization import json_dumps
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

LONG_RUNNING_TASK_ENTRYPOINT: Final[str] = "long_running_task"


async def _wait_for_task_to_finish(client: TestClient, task_id: TaskId):
    assert client.app
    status_url = client.app.router["get_task_status"].url_for(task_id=task_id)
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


TASK_CONTEXT: Final[dict[str, Any]] = {"user_id": 123}


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
            num_strings=query_params.num_strings,
            sleep_time=query_params.sleep_time,
            fail=query_params.fail,
            task_context=TASK_CONTEXT,
        )
        return web.json_response(
            data={"data": task_id},
            status=web.HTTPAccepted.status_code,
            dumps=json_dumps,
        )

    return routes


# WITH TASK CONTEXT
# NOTE: as the long running task framework may be used in any number of services
# in some cases there might be specific so-called task contexts.
# For instance in the webserver the tasks are linked to a specific user_id and product
# that is retrieved through some complex method
# all the subsequent routes to GET tasks or GET tasks/{task_id}, ... must only be
# retrieved if they satisfy to this context (i.e. only user_id=3 can see the tasks of user_id=3)


class _TestQueryParam(BaseModel):
    user_id: Optional[int] = None


def _pass_user_id_decorator(handler: Handler):
    @wraps(handler)
    async def _test_task_context_decorator(request: web.Request) -> web.StreamResponse:
        """this task context callback tries to get the user_id from the query if available"""
        query_param = parse_request_query_parameters_as(_TestQueryParam, request)
        request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY] = query_param.dict()
        return await handler(request)

    return _test_task_context_decorator


@pytest.fixture
def app_with_task_context(server_routes: web.RouteTableDef) -> web.Application:
    app = web.Application()
    app.add_routes(server_routes)
    # this adds enveloping and error middlewares
    append_rest_middlewares(app, api_version="")
    long_running_tasks.server.setup(
        app,
        router_prefix="/futures_with_task_context",
        task_request_context_decorator=_pass_user_id_decorator,
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


async def test_list_tasks_with_context(client_with_task_context: TestClient):
    assert client_with_task_context.app
    url = (
        client_with_task_context.app.router[LONG_RUNNING_TASK_ENTRYPOINT]
        .url_for()
        .update_query(num_strings=10, sleep_time=f"{0.2}")
    )
    resp = await client_with_task_context.post(f"{url}")
    task_id, error = await assert_status(resp, web.HTTPAccepted)
    assert task_id
    assert not error

    # the list should be empty if we do not pass the expected context
    list_url = client_with_task_context.app.router["list_tasks"].url_for()
    result = await client_with_task_context.get(f"{list_url}")
    data, error = await assert_status(result, web.HTTPOk)
    assert not error
    list_of_tasks = parse_obj_as(list[TaskGet], data)
    assert len(list_of_tasks) == 0

    # the list should be full if we pass the expected context
    result = await client_with_task_context.get(
        f"{list_url.update_query(TASK_CONTEXT)}"
    )
    data, error = await assert_status(result, web.HTTPOk)
    assert not error
    list_of_tasks = parse_obj_as(list[TaskGet], data)
    assert len(list_of_tasks) == 1
