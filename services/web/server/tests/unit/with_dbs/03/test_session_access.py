# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from simcore_service_webserver.session import (
    _setup_encrypted_cookie_sessions,
    generate_fernet_secret_key,
)
from simcore_service_webserver.session_access import (
    session_access_constraint,
    session_access_trace,
)


@pytest.fixture
def contraint_max_access_count() -> int:
    return 1


@pytest.fixture
def client(event_loop, aiohttp_client, contraint_max_access_count: int) -> TestClient:
    routes = web.RouteTableDef()

    @routes.get("/a", name="get_a")
    @session_access_trace("get_a")  # <---- TRACE
    async def get_a(request: web.Request):
        return web.Response(text="A")

    @routes.get("/b", name="get_b")
    @session_access_trace("get_b")  # <---- TRACE
    async def get_b(request: web.Request):
        return web.Response(text="B")

    @routes.get("/c", name="get_c")
    @session_access_constraint(  # <---- CONTRAINT
        allow_access_after=["get_a", "get_b"],
        max_number_of_access=contraint_max_access_count,
    )
    async def get_c(request: web.Request):
        return web.Response(text="C")

    @routes.get("/d", name="get_d")
    async def get_d(request: web.Request):
        return web.Response(text="D")

    #
    # get_a ---->|
    #            | get_C
    # get_b ---->|
    #
    # get_d ---->
    #
    app = web.Application()

    _setup_encrypted_cookie_sessions(
        app=app,
        secret_key=generate_fernet_secret_key(),
    )

    app.add_routes(routes)
    return event_loop.run_until_complete(aiohttp_client(app))


async def test_c_grants_access_after_a(client: TestClient):
    response = await client.get("/a")  # produces
    assert response.ok

    response = await client.get("/c")  # consumes
    assert response.ok


async def test_c_grants_access_after_b(client: TestClient):
    response = await client.get("/b")  # produces
    assert response.ok

    response = await client.get("/c")  # consumes
    assert response.ok


async def test_c_grants_access_after_b_and_then_ba(client: TestClient):
    response = await client.get("/b")  # produces
    assert response.ok

    response = await client.get("/c")  # consumes
    assert response.ok

    response = await client.get("/b")  # produces
    assert response.ok
    response = await client.get("/a")  # produces
    assert response.ok

    response = await client.get("/c")  # consumes
    assert response.ok


async def test_c_grants_access_after_b_and_non_traced(client: TestClient):
    response = await client.get("/b")  # produces
    assert response.ok

    # can have calls in the middle that are not traced?
    for _ in range(3):
        response = await client.get("/d")
        assert response.ok

    response = await client.get("/c")  # consumes
    assert response.ok


async def test_c_fails_access_alone(client: TestClient):
    response = await client.get("/c")
    assert not response.ok


async def test_c_fails_access_after_d(client: TestClient):
    response = await client.get("/d")
    assert response.ok

    response = await client.get("/c")
    assert not response.ok


async def test_c_fails_access_after_once(client: TestClient):
    response = await client.get("/a")
    assert response.ok

    response = await client.get("/c")
    assert response.ok

    for _ in range(3):
        response = await client.get("/c")
        assert not response.ok


@pytest.mark.parametrize("contraint_max_access_count", (1, 2, 5))
async def test_max_access_count_option(
    client: TestClient, contraint_max_access_count: int
):
    response = await client.get("/a")
    assert response.ok

    for _ in range(contraint_max_access_count):
        response = await client.get("/c")
        assert response.ok

    response = await client.get("/c")
    assert not response.ok
