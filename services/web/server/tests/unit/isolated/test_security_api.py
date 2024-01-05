from collections.abc import Callable

from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp_security import check_authorized, check_permission
from aiohttp_session import get_session
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from simcore_service_webserver._constants import APP_DB_ENGINE_KEY
from simcore_service_webserver.security.api import (
    forget_identity_in_session,
    remember_identity_in_session,
)
from simcore_service_webserver.security.plugin import setup_security


async def client(aiohttp_client: Callable):
    async def _login(request: web.Request):
        body = await request.json()

        email = parse_obj_as(LowerCaseEmailStr, body["email"])
        product = parse_obj_as(ProductName, body["product"])

        if body.get("password") != "secret":
            raise web.HTTPUnauthorized(reason="wrong password")

        # username, product_name, password or 2FA -> yes, this product exist
        # can username use this product # Auth!
        # user identity granted
        # product identity confirmed

        # has user access to product?

        # permission in this product?
        session = await get_session(request)
        session["product"] = product

        return await remember_identity_in_session(
            request,
            web.HTTPOk(),
            user_email=email,
        )

    async def _public(request: web.Request):
        return web.HTTPOk()

    async def _protected(request: web.Request):
        await check_authorized(request)  # = you are logged in
        await check_permission(request, "admin.*")

        return web.HTTPOk()

    async def _logout(request: web.Request):
        await check_authorized(request)

        # permission?
        session = await get_session(request)
        session.pop("product", None)

        return await forget_identity_in_session(
            request,
            web.HTTPOk(),
        )

    app = web.Application()

    # setup_db(app)
    app[APP_DB_ENGINE_KEY] = None
    setup_security(app)

    app.add_routes(
        [
            web.post("/login", _login),
            web.post("/public", _public),
            web.post("/protected", _protected),
            web.post("/logout", _logout),
        ]
    )

    return await aiohttp_client(app)


async def test_it(client: TestClient, mocker: MockerFixture):
    # Tests start here

    get_active_user_or_none_mock = mocker.patch(
        "simcore_service_webserver.security._authz.get_active_user_or_none",
        autospec=True,
    )

    r = await client.post(
        "/login",
        json={"email": "foo@email.com", "password": "secret", "product": "osparc"},
    )
    assert r.ok
    assert get_active_user_or_none_mock.called

    await client.post("/public")
    assert r.ok

    await client.post("/protected")
    assert r.ok

    await client.post("/logout")
    assert r.ok
