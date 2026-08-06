# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
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

    registered_routes = {route.resource.canonical for route in client.app.router.routes() if route.resource}
    assert f"/{API_VTAG}/test-helpers" in registered_routes

    return client


async def _test_helpers_handler(request: web.Request):
    product_name = products_web.get_product_name(request)
    current_product = products_web.get_current_product(request)

    assert current_product.name == product_name

    credit_price_info = await products_web.get_current_product_credit_price_info(request)
    assert credit_price_info is None

    return web.json_response(
        {
            "current_product": current_product.model_dump(mode="json"),
            "product_name": product_name,
            "credit_price_info": credit_price_info,
        }
    )


async def test_request_helpers(client: TestClient, default_product_name: ProductName):
    resp = await client.get(
        f"/{API_VTAG}/test-helpers",
        headers={X_PRODUCT_NAME_HEADER: default_product_name},
    )

    assert resp.ok, f"Got {await resp.text()}"

    got = await resp.json()
    assert got["product_name"] == default_product_name
