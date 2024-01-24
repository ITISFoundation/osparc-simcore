# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.web import RouteTableDef
from aiohttp_security import check_authorized
from aiohttp_session import get_session
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.products import LOGIN_SETTINGS_DEFAULT, products
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.products._events import _set_app_state
from simcore_service_webserver.products._middlewares import discover_product_middleware
from simcore_service_webserver.products._model import Product
from simcore_service_webserver.security.api import (
    check_permission,
    clean_auth_policy_cache,
    forget_identity,
    remember_identity,
)
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.settings import SessionSettings

# Prototype concept -------------------------------------------------------
#
# - remember/forget are verbs that refers to statefull sessions
# - get borrowed from dict/maps
#
_SESSION_PRODUCT_NAME_KEY = "product_name"


async def _remember_product_name(request: web.Request, product: ProductName):
    session = await get_session(request)
    session[_SESSION_PRODUCT_NAME_KEY] = product


async def _get_product_name(request: web.Request) -> ProductName | None:
    session = await get_session(request)
    return session.get(_SESSION_PRODUCT_NAME_KEY, None)


async def _forget_product_name(request: web.Request) -> ProductName | None:
    session = await get_session(request)
    return session.pop(_SESSION_PRODUCT_NAME_KEY, None)


# ------------------------------------------------------------------------


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
def expected_product_name():
    return "tis"


@pytest.fixture
def app_products(expected_product_name: ProductName) -> OrderedDict[str, Product]:
    column_defaults: dict[str, Any] = {
        c.name: f"{c.server_default.arg}" for c in products.columns if c.server_default
    }
    column_defaults["login_settings"] = LOGIN_SETTINGS_DEFAULT

    pp: OrderedDict[str, Product] = OrderedDict()
    pp[expected_product_name] = Product(
        name=expected_product_name,
        host_regex=expected_product_name,
        **column_defaults,
    )
    assert expected_product_name not in {"osparc", "s4l"}

    pp["osparc"] = Product(
        name="osparc",
        host_regex="osparc",
        **column_defaults,
    )
    pp["s4l"] = Product(
        name="s4l",
        host_regex="s4l",
        **column_defaults,
    )
    return pp


@pytest.fixture
def app_routes(
    expected_product_name: ProductName, app_products: OrderedDict[str, Product]
) -> RouteTableDef:
    assert "v0" == API_VTAG

    routes = RouteTableDef()

    @routes.post("/v0/login")
    async def _login(request: web.Request):
        body = await request.json()
        email = parse_obj_as(LowerCaseEmailStr, body["email"])
        product_name = parse_obj_as(ProductName, body["product"])

        # Authentication takes place here
        if body.get("password") != "secret":
            raise web.HTTPUnauthorized(reason="wrong password")

        # Product identity confirmed
        if product_name not in app_products:
            raise web.HTTPUnprocessableEntity(reason="wrong product")

        # Permission in this product: Has user access to product?
        # raise web.HTTPForbidden

        # if all good, let's update session with
        await _remember_product_name(request, product_name)
        return await remember_identity(
            request,
            web.HTTPOk(),
            user_email=email,
        )

    @routes.post("/v0/public")
    async def _public(request: web.Request):
        # NOTE: this will not be true if login is not done!
        assert await _get_product_name(request) == expected_product_name

        return web.HTTPOk()

    @routes.post("/v0/protected")
    async def _protected(request: web.Request):
        await check_authorized(request)  # = you are logged in
        await check_permission(request, "admin.*")

        assert await _get_product_name(request) == expected_product_name

        return web.HTTPOk()

    @routes.post("/v0/logout")
    async def _logout(request: web.Request):
        await check_authorized(request)

        product_name = await _forget_product_name(request)
        assert product_name == expected_product_name

        return await forget_identity(request, web.HTTPOk())

    return routes


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    mocker: MockerFixture,
    app_products: OrderedDict[str, Product],
    set_products_in_app_state: Callable[
        [web.Application, OrderedDict[str, Product]], None
    ],
    app_routes: RouteTableDef,
    mock_env_devel_environment: EnvVarsDict,
):
    app = web.Application()
    app.router.add_routes(app_routes)

    # mocks 'setup_session': patch to avoid setting up all ApplicationSettings
    session_settings = SessionSettings.create_from_envs()
    print(session_settings.json(indent=1))
    mocker.patch(
        "simcore_service_webserver.session.plugin.get_plugin_settings",
        autospec=True,
        return_value=session_settings,
    )

    setup_security(app)

    # mocks 'setup_products': patch to avoid database
    set_products_in_app_state(app, app_products)
    app.middlewares.append(discover_product_middleware)

    return event_loop.run_until_complete(aiohttp_client(app))


async def test_user_session(client: TestClient, mocker: MockerFixture):
    assert client.app
    # NOTE: this might be a problem with every test since cache is global per process
    await clean_auth_policy_cache(client.app)

    mocker.patch(
        "simcore_service_webserver.security._authz.get_database_engine",
        autospec=True,
    )
    get_active_user_or_none_mock = mocker.patch(
        "simcore_service_webserver.security._authz.get_active_user_or_none",
        autospec=True,
        return_value={"email": "foo@email.com", "id": 1, "role": UserRole.ADMIN},
    )

    resp = await client.post(
        "/v0/login",
        json={
            "email": "foo@email.com",
            "password": "secret",
            "product": "tis",
        },
    )
    assert resp.ok

    resp = await client.post("/v0/public")
    assert resp.ok, f"error: {await resp.text()}"
    assert not get_active_user_or_none_mock.called

    resp = await client.post("/v0/protected")
    assert resp.ok, f"error: {await resp.text()}"
    assert get_active_user_or_none_mock.called

    resp = await client.post("/v0/logout")
    assert resp.ok, f"error: {await resp.text()}"
