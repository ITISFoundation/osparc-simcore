# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from asyncio import AbstractEventLoop
from typing import Callable

import pytest
from aiohttp import web
from aiohttp.client_reqrep import ClientResponse
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.rest_responses import _collect_http_exceptions
from servicelib.aiohttp.tracing import setup_tracing

DEFAULT_JAEGER_BASE_URL = "http://jaeger:9411"


@pytest.fixture()
def client(
    loop: AbstractEventLoop, aiohttp_client: Callable, unused_tcp_port_factory: Callable
) -> TestClient:
    ports = [unused_tcp_port_factory() for _ in range(2)]

    async def redirect(request: web.Request) -> web.Response:
        return web.HTTPFound(location="/return/200")

    async def return_response(request: web.Request) -> web.Response:
        code = int(request.match_info["code"])
        return web.Response(status=code)

    async def raise_response(request: web.Request):
        status_code = int(request.match_info["code"])
        status_to_http_exception = _collect_http_exceptions()
        http_exception_cls = status_to_http_exception[status_code]
        raise http_exception_cls(
            reason=f"raised from raised_error with code {status_code}"
        )

    async def skip(request: web.Request):
        return web.HTTPServiceUnavailable(reason="should not happen")

    app = web.Application()
    app.add_routes(
        [
            web.get("/redirect", redirect),
            web.get("/return/{code}", return_response),
            web.get("/raise/{code}", raise_response),
            web.get("/skip", skip, name="skip"),
        ]
    )

    print("Resources:")
    for resource in app.router.resources():
        print(resource)

    # UNDER TEST ---
    # SEE RoutesView to understand how resources can be iterated to get routes
    resource = app.router["skip"]
    routes_in_a_resource = list(resource)

    setup_tracing(
        app,
        service_name=f"{__name__}.client",
        host="127.0.0.1",
        port=ports[0],
        jaeger_base_url=DEFAULT_JAEGER_BASE_URL,
        skip_routes=routes_in_a_resource,
    )

    return loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": ports[0]})
    )


async def test_setup_tracing(client: TestClient):
    res: ClientResponse

    # on error
    for code in (web.HTTPOk.status_code, web.HTTPBadRequest.status_code):
        res = await client.get(f"/return/{code}")

        assert res.status == code, await res.text()
        res = await client.get(f"/raise/{code}")
        assert res.status == code, await res.text()

    res = await client.get("/redirect")
    # TODO: check it was redirected
    assert res.status == 200, await res.text()

    res = await client.get("/skip")
    assert res.status == web.HTTPServiceUnavailable.status_code

    # using POST instead of GET ->  HTTPMethodNotAllowed
    res = await client.post("/skip")
    assert res.status == web.HTTPMethodNotAllowed.status_code, "GET and not POST"
