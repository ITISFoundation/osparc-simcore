# pylint: disable=redefined-outer-name

import asyncio
from typing import Callable

import pytest
from aiohttp import ClientResponseError, web
from aiohttp.test_utils import TestClient
from servicelib.aiohttp import long_running_tasks
from servicelib.aiohttp.long_running_tasks.client import long_running_task_request
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


async def test_long_running_task_request(
    client: TestClient, long_running_task_entrypoint: str
):
    assert client.app
    request = client.app.router[long_running_task_entrypoint].url_for()

    # missing parameters raises
    with pytest.raises(ClientResponseError):
        async for _ in long_running_task_request(client, request, None):
            ...
    async for _ in long_running_task_request(
        client, request.with_query(num_strings=10, sleep_time=1), data=None
    ):
        ...
