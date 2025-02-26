# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from simcore_service_webserver.constants import FRONTEND_APP_DEFAULT
from simcore_service_webserver.products import products_service
from simcore_service_webserver.products._repository import ProductRepository
from simcore_service_webserver.products.errors import ProductPriceNotDefinedError


@pytest.fixture
def app(
    client: TestClient,
) -> web.Application:
    # initialized app
    assert client.app
    return client.app


@pytest.fixture
def default_product_name() -> ProductName:
    return FRONTEND_APP_DEFAULT


async def test_get_product(app: web.Application, default_product_name: ProductName):

    product = products_service.get_product(app, product_name=default_product_name)
    assert product.name == default_product_name

    products = products_service.list_products(app)
    assert len(products) == 1
    assert products[0] == product


async def test_get_product_ui(app: web.Application, default_product_name: ProductName):
    # this feature is currently setup from adminer by an operator

    repo = ProductRepository.create_from_app(app)
    ui = await products_service.get_product_ui(repo, product_name=default_product_name)
    assert ui == {}, "Expected empty by default"


async def test_get_product_stripe_info(
    app: web.Application, default_product_name: ProductName
):
    # this feature is currently setup from adminer by an operator

    # default is not configured
    with pytest.raises(ValueError, match=default_product_name):
        await products_service.get_product_stripe_info(
            app, product_name=default_product_name
        )


async def test_get_credit_amount(
    app: web.Application, default_product_name: ProductName
):
    # this feature is currently setup from adminer by an operator

    # default is not configured
    with pytest.raises(ProductPriceNotDefinedError):
        await products_service.get_credit_amount(
            app, dollar_amount=1, product_name=default_product_name
        )
