# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections import OrderedDict
from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp_security import check_authorized, check_permission
from aiohttp_session import get_session
from cryptography.fernet import Fernet
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from simcore_service_webserver.products._events import _set_app_state
from simcore_service_webserver.products._middlewares import discover_product_middleware
from simcore_service_webserver.products._model import Product
from simcore_service_webserver.products.api import get_current_product
from simcore_service_webserver.security.api import forget_identity, remember_identity
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.settings import SessionSettings


#
# remember/forget are verbs that refers to statefull sessions
#
async def remember_product(request: web.Request, product: ProductName):
    session = await get_session(request)
    session["product_name"] = product


async def forget_product(request: web.Request):
    session = await get_session(request)
    return session.pop("product", None)


@pytest.fixture
def set_products_in_app_state() -> Callable[
    [web.Application, OrderedDict[str, Product]], None
]:
    """
    Add products in app's state to avoid setting up a full database in tests

        app: web.Application,
        app_products: OrderedDict[str, Product] with the first product being the default
    """

    def _(
        app: web.Application,
        app_products: OrderedDict[str, Product],
    ) -> None:
        first_product = next(iter(app_products.keys()))
        return _set_app_state(app, app_products, default_product_name=first_product)

    return _


@pytest.fixture
def client(
    loop,
    aiohttp_client: Callable,
    mocker: MockerFixture,
    set_products_in_app_state: Callable[
        [web.Application, OrderedDict[str, Product]], None
    ],
):
    # routes ----------

    async def _login(request: web.Request):
        body = await request.json()

        email = parse_obj_as(LowerCaseEmailStr, body["email"])
        product = parse_obj_as(ProductName, body["product"])

        get_current_product(request)

        # username, product_name, password or 2FA -> yes, this product exist
        # can username use this product # Auth!
        # user identity granted
        if body.get("password") != "secret":
            raise web.HTTPUnauthorized(reason="wrong password")

        # product identity confirmed

        # has user access to product?

        # permission in this product?
        await remember_product(request, product)

        return await remember_identity(
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

        product_name = await forget_product(request)
        assert product_name

        return await forget_identity(request, web.HTTPOk())

    app = web.Application()

    # mocks setup_session -----
    # patch to avoid setting up all ApplicationSettings
    mocker.patch(
        "simcore_service_webserver.session.plugin.get_plugin_settings",
        autospec=True,
        return_value=SessionSettings(
            SESSION_SECRET_KEY=Fernet.generate_key().decode("utf-8")
        ),  # type: ignore
    )

    setup_security(app)

    # mocks setup_products  -----
    app_products: OrderedDict[str, Product] = OrderedDict()  # TODO:
    set_products_in_app_state(app, app_products)
    app.middlewares.append(discover_product_middleware)

    app.add_routes(
        [
            web.post("/login", _login),
            web.post("/public", _public),
            web.post("/protected", _protected),
            web.post("/logout", _logout),
        ]
    )

    return loop.run_until_complete(aiohttp_client(app))


async def test_user_session(client: TestClient, mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.security._authz.get_database_engine",
        autospec=True,
    )
    get_active_user_or_none_mock = mocker.patch(
        "simcore_service_webserver.security._authz.get_active_user_or_none",
        autospec=True,
    )

    response = await client.post(
        "/login",
        json={
            "email": "foo@email.com",
            "password": "secret",
            "product": "osparc",
        },
    )
    assert response.ok

    await client.post("/public")
    assert response.ok

    await client.post("/protected")
    assert response.ok
    assert get_active_user_or_none_mock.called

    await client.post("/logout")
    assert response.ok
