# pylint: disable=redefined-outer-name

import asyncio
from typing import Callable, Optional

import pytest
from aiohttp import ClientResponseError, web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import long_running_tasks
from servicelib.aiohttp.long_running_tasks.client import (
    LRTask,
    long_running_task_request,
)
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares


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


async def test_long_running_task_request_raises_400(
    client: TestClient, long_running_task_entrypoint: str
):
    assert client.app
    url = client.app.router[long_running_task_entrypoint].url_for()

    # missing parameters raises
    with pytest.raises(ClientResponseError):
        async for _ in long_running_task_request(client, url, None):
            ...


async def test_long_running_task_request(
    client: TestClient, long_running_task_entrypoint: str
):
    assert client.app
    url = client.app.router[long_running_task_entrypoint].url_for()

    task: Optional[LRTask] = None
    async for task in long_running_task_request(
        client,
        url.with_query(num_strings=10, sleep_time=0.1),
        json=None,
        wait_interval_s=0.01,
    ):
        print(f"<-- received {task.progress=}, {task.result=}")
    assert task is not None
    assert task.result
    assert await task.result == [f"{x}" for x in range(10)]


async def test_long_running_task_request_timeout(
    client: TestClient, long_running_task_entrypoint: str
):
    assert client.app
    url = client.app.router[long_running_task_entrypoint].url_for()

    task: Optional[LRTask] = None
    with pytest.raises(asyncio.TimeoutError):
        async for task in long_running_task_request(
            client,
            url.with_query(num_strings=10, sleep_time=1),
            json=None,
            wait_interval_s=0.5,
            wait_timeout_s=2,
        ):
            print(f"<-- received {task.progress=}, {task.result=}")

    # check the task was properly aborted by the client
    list_url = client.app.router["list_tasks"].url_for()
    result = await client.get(f"{list_url}")
    data, error = await assert_status(result, web.HTTPOk)
    assert not error
    assert data == []


async def test_long_running_task_request_error(
    client: TestClient, long_running_task_entrypoint: str
):
    assert client.app
    url = client.app.router[long_running_task_entrypoint].url_for()

    task: Optional[LRTask] = None
    async for task in long_running_task_request(
        client,
        url.with_query(num_strings=10, sleep_time=0.1, fail=f"{True}"),
        json=None,
        wait_interval_s=0.01,
    ):
        print(f"<-- received {task.progress=}, {task.result=}")
    assert task is not None
    assert task.result
    with pytest.raises(ClientResponseError):
        await task.result
