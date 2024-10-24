# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
import statistics
from collections import OrderedDict
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.web import RouteTableDef
from aiohttp_session import get_session
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.products import LOGIN_SETTINGS_DEFAULT, products
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.login.decorators import login_required
from simcore_service_webserver.products._events import _set_app_state
from simcore_service_webserver.products._middlewares import discover_product_middleware
from simcore_service_webserver.products._model import Product
from simcore_service_webserver.security.api import (
    check_user_authorized,
    clean_auth_policy_cache,
    forget_identity,
    remember_identity,
)
from simcore_service_webserver.security.decorators import permission_required
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
    if product_name := session.get(_SESSION_PRODUCT_NAME_KEY, None):
        return product_name

    # NOTE: this or deduce from url
    raise web.HTTPUnauthorized(reason="Invalid session. Reload / first")


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
    pp["tis"] = Product(
        name="tis",
        host_regex="tis",
        **column_defaults,
    )
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

    assert expected_product_name in pp
    return pp


@pytest.fixture
def registered_users(expected_product_name: str):
    users = [
        {
            "email": "foo@email.com",
            "id": 1,
            "role": UserRole.ADMIN,
            "registered_products": {"osparc", expected_product_name},
        },
        {
            "email": "bar@email.com",
            "id": 2,
            "role": UserRole.ADMIN,
            "registered_products": {"osparc"},
        },
    ]
    return {u["email"]: u for u in users}


@pytest.fixture
def app_routes(
    expected_product_name: ProductName,
    app_products: OrderedDict[str, Product],
    registered_users: dict,
) -> RouteTableDef:
    assert API_VTAG == "v0"

    routes = RouteTableDef()

    @routes.get("/")
    async def _init(request: web.Request):
        # get url and deliver product
        product_name = expected_product_name
        await _remember_product_name(request, product_name)
        return web.json_response(status=status.HTTP_200_OK)

    @routes.post("/v0/hack/{product_name}")
    async def _set_other_product(request: web.Request):
        await _remember_product_name(request, request.match_info["product_name"])
        return web.json_response(status=status.HTTP_200_OK)

    @routes.post("/v0/login")
    async def _login(request: web.Request):
        product_name = await _get_product_name(request)
        body = await request.json()
        email = TypeAdapter(LowerCaseEmailStr).validate_python(body["email"])

        # Permission in this product: Has user access to product?
        if product_name not in registered_users[email]["registered_products"]:
            raise web.HTTPForbidden(reason="no access to this product")

        # Authentication takes place here
        if body.get("password") != "secret":
            raise web.HTTPUnauthorized(reason="wrong password")

        # if all good, let's update session with
        return await remember_identity(request, web.HTTPOk(), user_email=email)

    @routes.post("/v0/public")
    async def _public(request: web.Request):
        assert await _get_product_name(request) == expected_product_name
        return web.json_response(status=status.HTTP_200_OK)

    @routes.post("/v0/admin")
    @login_required  # NOTE: same as `await check_user_authorized(request)``
    @permission_required(
        "admin.*"  # NOTE: same as `await check_user_permission(request, "admin.*")``
    )
    async def _admin_only(request: web.Request):
        assert await _get_product_name(request) == expected_product_name
        return web.json_response(status=status.HTTP_200_OK)

    @routes.post("/v0/logout")
    async def _logout(request: web.Request):
        await check_user_authorized(request)
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
    print(session_settings.model_dump_json(indent=1))
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


@pytest.fixture
async def basic_db_funs_mocked(client: TestClient, mocker: MockerFixture) -> None:
    assert client.app
    # NOTE: this might be a problem with every test since cache is global per process
    await clean_auth_policy_cache(client.app)

    mocker.patch(
        "simcore_service_webserver.security._authz_policy.get_database_engine",
        autospec=True,
    )


async def test_product_in_session(
    client: TestClient,
    expected_product_name: ProductName,
    basic_db_funs_mocked: None,
):

    resp = await client.post("/v0/public")
    assert resp.status == status.HTTP_401_UNAUTHORIZED, f"error: {await resp.text()}"

    # inits session by getting front-end
    resp = await client.get("/")
    assert resp.ok, f"error: {await resp.text()}"

    resp = await client.post("/v0/public")
    assert resp.ok, f"error: {await resp.text()}"


@pytest.fixture
def get_active_user_or_none_dbmock(
    basic_db_funs_mocked: None, mocker: MockerFixture
) -> MagicMock:
    return mocker.patch(
        "simcore_service_webserver.security._authz_policy.get_active_user_or_none",
        autospec=True,
        return_value={"email": "foo@email.com", "id": 1, "role": UserRole.ADMIN},
    )


@pytest.fixture
def is_user_in_product_name_dbmock(
    basic_db_funs_mocked: None, mocker: MockerFixture
) -> MagicMock:
    return mocker.patch(
        "simcore_service_webserver.security._authz_policy.is_user_in_product_name",
        autospec=True,
        return_value=True,
    )


async def test_auth_in_session(
    client: TestClient,
    expected_product_name: ProductName,
    get_active_user_or_none_dbmock: MagicMock,
    is_user_in_product_name_dbmock: MagicMock,
):
    # inits session by getting front-end
    resp = await client.get("/")
    assert resp.ok, f"error: {await resp.text()}"

    # login 'bar' (has no access to product)
    resp = await client.post(
        "/v0/login",
        json={
            "email": "bar@email.com",
            "password": "secret",
        },
    )
    assert resp.status == status.HTTP_403_FORBIDDEN

    # login 'foo' (has access to product)
    resp = await client.post(
        "/v0/login",
        json={
            "email": "foo@email.com",
            "password": "secret",
        },
    )
    assert resp.ok

    resp = await client.post("/v0/public")
    assert resp.ok, f"error: {await resp.text()}"
    assert not get_active_user_or_none_dbmock.called

    resp = await client.post("/v0/admin")
    assert resp.ok, f"error: {await resp.text()}"
    assert get_active_user_or_none_dbmock.called

    resp = await client.post("/v0/logout")
    assert resp.ok, f"error: {await resp.text()}"

    # after logout
    resp = await client.post("/v0/public")
    assert resp.ok, f"error: {await resp.text()}"

    resp = await client.post("/v0/admin")
    assert resp.status == status.HTTP_401_UNAUTHORIZED, f"error: {await resp.text()}"

    resp = await client.post("/v0/logout")
    assert resp.status == status.HTTP_401_UNAUTHORIZED, f"error: {await resp.text()}"


async def test_hack_product_session(
    client: TestClient,
    get_active_user_or_none_dbmock: MagicMock,
    is_user_in_product_name_dbmock: MagicMock,
):

    resp = await client.post("/v0/hack/s4l")
    assert resp.ok

    # not logged in
    resp = await client.post("/v0/admin")
    assert resp.status == status.HTTP_401_UNAUTHORIZED

    # login 'foo' (w/o access to s4l)
    resp = await client.post(
        "/v0/login",
        json={
            "email": "foo@email.com",
            "password": "secret",
        },
    )
    assert resp.status == status.HTTP_403_FORBIDDEN


@pytest.fixture
async def session_initialized(
    client: TestClient,
    basic_db_funs_mocked: None,
) -> None:
    assert client.app

    # init
    resp = await client.get("/")
    assert resp.ok, f"error: {await resp.text()}"

    # login
    resp = await client.post(
        "/v0/login",
        json={
            "email": "foo@email.com",
            "password": "secret",
        },
    )
    assert resp.ok, f"error: {await resp.text()}"

    await clean_auth_policy_cache(client.app)


async def test_number_of_db_calls_on_handlers_of_auth_decorators(
    client: TestClient,
    session_initialized: None,
    get_active_user_or_none_dbmock: MagicMock,
    is_user_in_product_name_dbmock: MagicMock,
):
    """test overhead of adding @login_required and @permission_required to a handler"""
    assert client.app

    # reference: eval w/o decorators
    resp = await client.post("/v0/public")
    assert resp.ok, f"error: {await resp.text()}"

    # Number of times db functions are called in one request
    assert get_active_user_or_none_dbmock.call_count == 0
    assert is_user_in_product_name_dbmock.call_count == 0

    # under test: eval w/ auth *_required decorators
    resp = await client.post("/v0/admin")

    assert resp.ok, f"error: {await resp.text()}"

    # Number of times db functions are called in one request
    assert get_active_user_or_none_dbmock.call_count == 1
    assert is_user_in_product_name_dbmock.call_count == 1


async def test_time_overhead_on_handlers_of_auth_decorators(
    client: TestClient,
    session_initialized: None,
    get_active_user_or_none_dbmock: MagicMock,
    is_user_in_product_name_dbmock: MagicMock,
):
    async def _req(url_):
        start = asyncio.get_event_loop().time()
        resp = await client.post(url_)
        stop = asyncio.get_event_loop().time()

        assert resp.ok, f"error: {await resp.text()}"
        return stop - start

    num_of_rounds = 100
    public_elapsed_times = [await _req("/v0/public") for _ in range(num_of_rounds)]
    admin_elapsed_times = [await _req("/v0/admin") for _ in range(num_of_rounds)]

    # SEE https://docs.python.org/3/library/statistics.html#function-details
    # Note The mean is strongly affected by outliers and is not necessarily a typical example of the data points.
    # For a more robust, although less efficient, measure of central tendency, see median().
    ref_elapsed = statistics.median(public_elapsed_times)
    elapsed = statistics.median(admin_elapsed_times)

    # NOTE: 150% more wrt reference (basically ~ 2.5x more !!!!!!!!!!!)
    # and this is mocking the access to the database!
    msg = f"got {elapsed/ref_elapsed=} from medians {elapsed=} and {ref_elapsed=} after {num_of_rounds=}"
    print(msg.capitalize())
    assert elapsed < ref_elapsed * (1 + 1.6), msg
