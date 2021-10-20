# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from asyncio import AbstractEventLoop
from typing import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.tracing import DEFAULT_JAEGER_BASE_URL, setup_tracing


@pytest.fixture()
def client(
    loop: AbstractEventLoop, aiohttp_client: Callable, aiohttp_unused_port: Callable
) -> TestClient:
    ports = [aiohttp_unused_port() for _ in range(2)]

    async def ok(request: web.Request) -> web.Response:
        return web.HTTPOk()

    async def fail_with(request: web.Request) -> web.Response:
        code = int(request.match_info["code"])
        return web.Response(status=code)

    app = web.Application()
    app.add_routes(
        [
            web.get("/ok", ok),
            web.get("/fail/{code}", fail_with),
        ]
    )

    print("Resources:")
    for resource in app.router.resources():
        print(resource)

    # UNDER TEST ---
    setup_tracing(
        app,
        service_name=f"{__name__}.client",
        host="127.0.0.1",
        port=ports[0],
        jaeger_base_url=DEFAULT_JAEGER_BASE_URL,
    )

    return loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": ports[0]})
    )


async def test_it(client: TestClient):

    # res = await client.get("/ok")
    # assert res.status == web.HTTPOk.status_code

    # for code in range(400, 500):
    #     res = await client.get(f"/fail/{code}")
    #     assert res.status == code

    # POST instead of GET --> HTTPM
    res = await client.post("/ok")
    assert res.status == web.HTTPMethodNotAllowed.status_code, "GET and not POST"
