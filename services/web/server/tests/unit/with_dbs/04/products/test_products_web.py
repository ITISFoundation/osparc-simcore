# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from common_library.json_serialization import json_dumps
from models_library.products import ProductName
from pytest_mock import MockerFixture, MockType
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.products import products_web
from simcore_service_webserver.products.plugin import setup_products


@pytest.fixture
def setup_products_mocked(mocker: MockerFixture) -> MockType:
    def _wrap(app: web.Application):
        setup_products(app)

        # register test handlers
        app.router.add_get(
            f"/{API_VTAG}/test-helpers",
            _test_helpers_handler,
            name=_test_helpers_handler.__name__,
        )
        app.router.add_get(
            f"/{API_VTAG}/test-product-template-helpers",
            _test_product_template_handler,
            name=_test_product_template_handler.__name__,
        )

        return True

    return mocker.patch(
        "simcore_service_webserver.application.setup_products",
        autospec=True,
        side_effect=_wrap,
    )


@pytest.fixture
def client(
    setup_products_mocked: MockType,  # keep before client fixture!
    client: TestClient,
) -> TestClient:
    assert setup_products_mocked.called

    assert client.app
    assert client.app.router

    registered_routes = {
        route.resource.canonical
        for route in client.app.router.routes()
        if route.resource
    }
    assert f"/{API_VTAG}/test-helpers" in registered_routes

    return client


async def _test_helpers_handler(request: web.Request):
    product_name = products_web.get_product_name(request)
    current_product = products_web.get_current_product(request)

    assert current_product.name == product_name

    credit_price_info = await products_web.get_current_product_credit_price_info(
        request
    )
    assert credit_price_info is None

    return web.json_response(
        json_dumps(
            {
                "current_product": current_product,
                "get_producproduct_namet_name": product_name,
                "credit_price_info": credit_price_info,
            }
        )
    )


async def test_request_helpers(client: TestClient, default_product_name: ProductName):

    resp = await client.get(
        f"/{API_VTAG}/test-helpers",
        headers={X_PRODUCT_NAME_HEADER: default_product_name},
    )

    assert resp.ok, f"Got {await resp.text()}"

    got = await resp.json()
    assert got["current_product"] == default_product_name


async def _test_product_template_handler(request: web.Request):
    product_name = products_web.get_product_name(request)

    # if no product, it should return common

    # if no template for product, it should return common
    # template/common/close_account.jinja2"
    template_path = await products_web.get_product_template_path(
        request, filename="close_account.jinja2"
    )
    assert template_path.exists()
    assert template_path.name == "close_account.jinja2"
    assert "common/" in f"{template_path.resolve().absolute()}"

    # if specific template, it gets and caches in file
    # "templates/osparc/registration_email.jinja2"
    template_path = await products_web.get_product_template_path(
        request, filename="registration_email.jinja2"
    )
    assert template_path.exists()
    assert template_path.name == "registration_email.jinja2"
    assert f"{product_name}/" in f"{template_path.resolve().absolute()}"

    # get again and should use file

    for _ in range(2):
        got = await products_web.get_product_template_path(
            request, filename="registration_email.jinja2"
        )
        assert got == template_path

    path = await products_web.get_product_template_path(
        request, filename="invalid-template-name.jinja"
    )
    assert path
    return web.json_response()


async def test_product_template_helpers(
    client: TestClient, default_product_name: ProductName
):

    resp = await client.get(
        f"/{API_VTAG}/test-product-template-helpers",
        headers={X_PRODUCT_NAME_HEADER: default_product_name},
    )

    assert resp.ok, f"Got {await resp.text()}"


async def test_get_product_template_path_without_product():
    fake_request = make_mocked_request("GET", "/fake", app=web.Application())

    # if no product, it should return common
    template_path = await products_web.get_product_template_path(
        fake_request, filename="close_account.jinja2"
    )

    assert template_path.exists()
    assert template_path.name == "close_account.jinja2"
    assert "common/" in f"{template_path.resolve().absolute()}"
