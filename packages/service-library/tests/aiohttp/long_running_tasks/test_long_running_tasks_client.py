# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from collections.abc import Callable

import pytest
from aiohttp import ClientResponseError, web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import long_running_tasks, status
from servicelib.aiohttp.long_running_tasks import client as lr_client
from servicelib.aiohttp.long_running_tasks.client import (
    LRTask,
    long_running_task_request,
)
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares
from settings_library.redis import RedisSettings
from yarl import URL

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app(
    server_routes: web.RouteTableDef, redis_service: RedisSettings
) -> web.Application:
    app = web.Application()
    app.add_routes(server_routes)
    # this adds enveloping and error middlewares
    append_rest_middlewares(app, api_version="")
    long_running_tasks.server.setup(
        app, redis_settings=redis_service, namespace="test", router_prefix="/futures"
    )

    return app


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    app: web.Application,
) -> TestClient:
    return await aiohttp_client(app, server_kwargs={"port": unused_tcp_port_factory()})


@pytest.fixture
def long_running_task_url(client: TestClient, long_running_task_entrypoint: str) -> URL:
    assert client.app
    return client.make_url(
        f"{client.app.router[long_running_task_entrypoint].url_for()}"
    )


async def test_long_running_task_request_raises_400(
    client: TestClient, long_running_task_url: URL
):
    # missing parameters raises
    with pytest.raises(ClientResponseError):
        async for _ in long_running_task_request(
            client.session, long_running_task_url, None
        ):
            ...


@pytest.fixture
def short_poll_interval(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        lr_client,
        "DEFAULT_POLL_INTERVAL_S",
        0.01,
    )


async def test_long_running_task_request(
    short_poll_interval, client: TestClient, long_running_task_url: URL
):
    task: LRTask | None = None
    async for task in long_running_task_request(
        client.session,
        long_running_task_url.with_query(num_strings=10, sleep_time=0.1),
        json=None,
    ):
        print(f"<-- received {task=}")
        if task.done():
            assert await task.result() == [f"{x}" for x in range(10)]

    assert task is not None


async def test_long_running_task_request_timeout(
    client: TestClient, long_running_task_url: URL
):
    assert client.app
    task: LRTask | None = None
    with pytest.raises(asyncio.TimeoutError):
        async for task in long_running_task_request(
            client.session,
            long_running_task_url.with_query(num_strings=10, sleep_time=1),
            json=None,
            client_timeout=2,
        ):
            print(f"<-- received {task=}")

    # check the task was properly aborted by the client
    list_url = client.app.router["list_tasks"].url_for()
    result = await client.get(f"{list_url}")
    data, error = await assert_status(result, status.HTTP_200_OK)
    assert not error
    assert data == []


async def test_long_running_task_request_error(
    client: TestClient, long_running_task_url: URL
):
    assert client.app
    task: LRTask | None = None
    async for task in long_running_task_request(
        client.session,
        long_running_task_url.with_query(
            num_strings=10, sleep_time=0.1, fail=f"{True}"
        ),
        json=None,
    ):
        print(f"<-- received {task=}")
    assert task is not None
    with pytest.raises(ClientResponseError):
        await task.result()
