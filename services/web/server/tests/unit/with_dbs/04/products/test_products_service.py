# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from itertools import product

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from common_library.users_enums import UserRole
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.products import products_service, products_web


@pytest.fixture(params=["osparc", "tis", "s4l"])
def product_name(request: pytest.FixtureRequest) -> ProductName:
    return request.param


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.PRODUCT_OWNER


@pytest.fixture
def app(
    logged_user: UserInfoDict,
    client: TestClient,
) -> web.Application:
    # TODO: remove client here
    assert client.app
    return client.app


async def test_get_credit_amount(product_name: ProductName, app: web.Application):
    await products_service.get_credit_amount(
        app, dollar_amount=1, product_name=product_name
    )


async def test_get_product(product_name: ProductName, app: web.Application):
    product = products_service.get_product(app, product_name=product_name)
    assert product.name == product_name


async def test_get_product_stripe_info(product_name: ProductName, app: web.Application):
    await products_service.get_product_stripe_info(app, product_name=product_name)


async def test_get_product_ui(product_name: ProductName, app: web.Application):

    await products_service.get_product_ui(app, product_name=product_name)


async def test_list_products(app: web.Application):
    products_service.list_products(app)


@pytest.fixture
def fake_request(
    app: web.Application,
    product_name: ProductName,
) -> web.Request:
    return make_mocked_request(
        "GET",
        "/fake",
        headers={X_PRODUCT_NAME_HEADER: product_name},
        app=app,
    )


async def test_get_current_product(
    product_name: ProductName, fake_request: web.Request
):
    product = products_web.get_current_product(fake_request)
    assert product.name == product_name


async def test_get_current_product_credit_price_info(
    product_name: ProductName, fake_request: web.Request
):
    await products_web.get_current_product_credit_price_info(fake_request)


async def test_get_product_name(
    product_name: ProductName,
    fake_request: web.Request,
):
    assert products_web.get_product_name(fake_request) == product_name


async def test_get_product_template_path(
    product_name: ProductName,
    fake_request: web.Request,
):
    path = await products_web.get_product_template_path(
        fake_request, filename="template_name.jinja"
    )
    assert path
