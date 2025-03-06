# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from models_library.products import ProductName, ProductStripeInfoGet
from pydantic import TypeAdapter, ValidationError
from pytest_mock import MockerFixture
from servicelib.exceptions import InvalidConfig
from simcore_postgres_database.utils_products_prices import ProductPriceInfo
from simcore_service_webserver.products import _service, products_service
from simcore_service_webserver.products._repository import ProductRepository
from simcore_service_webserver.products.errors import (
    BelowMinimumPaymentError,
    MissingStripeConfigError,
    ProductNotFoundError,
    ProductPriceNotDefinedError,
    ProductTemplateNotFoundError,
)
from simcore_service_webserver.products.models import Product


@pytest.fixture
def app(
    web_server: TestServer,
) -> web.Application:
    # app initialized and server running
    assert web_server.app
    return web_server.app


async def test_load_products(app: web.Application):
    products = await _service.load_products(app)
    assert isinstance(products, list)
    assert all(isinstance(product, Product) for product in products)


async def test_load_products_validation_error(app: web.Application, mocker):
    mock_repo = mocker.patch(
        "simcore_service_webserver.products._service.ProductRepository.create_from_app"
    )

    try:
        TypeAdapter(int).validate_python("not-an-int")
    except ValidationError as validation_error:
        mock_repo.return_value.list_products.side_effect = validation_error

    with pytest.raises(InvalidConfig, match="Invalid product configuration in db"):
        await _service.load_products(app)


async def test_get_default_product_name(app: web.Application):
    default_product_name = await _service.get_default_product_name(app)
    assert isinstance(default_product_name, ProductName)


async def test_get_product(app: web.Application, default_product_name: ProductName):
    product = products_service.get_product(app, product_name=default_product_name)
    assert product.name == default_product_name

    products = products_service.list_products(app)
    assert len(products) == 1
    assert products[0] == product


async def test_products_on_uninitialized_app(default_product_name: ProductName):
    uninit_app = web.Application()
    with pytest.raises(ProductNotFoundError):
        _service.get_product(uninit_app, default_product_name)


async def test_list_products_names(app: web.Application):
    product_names = await products_service.list_products_names(app)
    assert isinstance(product_names, list)
    assert all(isinstance(name, ProductName) for name in product_names)


async def test_get_credit_price_info(
    app: web.Application, default_product_name: ProductName
):
    price_info = await _service.get_credit_price_info(
        app, product_name=default_product_name
    )
    assert price_info is None or isinstance(price_info, ProductPriceInfo)


async def test_get_product_ui(app: web.Application, default_product_name: ProductName):
    repo = ProductRepository.create_from_app(app)
    ui = await products_service.get_product_ui(repo, product_name=default_product_name)
    assert ui == {}, "Expected empty by default"

    with pytest.raises(ProductNotFoundError):
        await products_service.get_product_ui(repo, product_name="undefined")


async def test_get_credit_amount(
    app: web.Application, default_product_name: ProductName, mocker: MockerFixture
):
    # Test when ProductPriceNotDefinedError is raised
    with pytest.raises(ProductPriceNotDefinedError):
        await products_service.get_credit_amount(
            app, dollar_amount=1, product_name=default_product_name
        )


async def test_get_credit_amount_with_repo_faking_data(
    default_product_name: ProductName, mocker: MockerFixture
):
    # NO need of database since repo is mocked
    app = web.Application()

    # Mock the repository to return a valid price info
    mock_repo = mocker.patch(
        "simcore_service_webserver.products._service.ProductRepository.create_from_app"
    )

    async def _get_product_latest_price_info_or_none(*args, **kwargs):
        return ProductPriceInfo(
            usd_per_credit=Decimal("10.0"), min_payment_amount_usd=Decimal("5.0")
        )

    mock_repo.return_value.get_product_latest_price_info_or_none.side_effect = (
        _get_product_latest_price_info_or_none
    )

    # Test when BelowMinimumPaymentError is raised
    with pytest.raises(BelowMinimumPaymentError):
        await products_service.get_credit_amount(
            app, dollar_amount=Decimal("3.0"), product_name=default_product_name
        )

    # Test when CreditResultGet is returned successfully
    credit_result = await products_service.get_credit_amount(
        app, dollar_amount=Decimal("10.0"), product_name=default_product_name
    )
    assert credit_result.credit_amount == Decimal("1.0")
    assert credit_result.product_name == default_product_name


async def test_get_product_stripe_info(
    app: web.Application, default_product_name: ProductName
):
    # database has no info
    with pytest.raises(MissingStripeConfigError, match=default_product_name):
        await products_service.get_product_stripe_info(
            app, product_name=default_product_name
        )


async def test_get_product_stripe_info_with_repo_faking_data(
    default_product_name: ProductName, mocker: MockerFixture
):
    # NO need of database since repo is mocked
    app = web.Application()

    # Mock the repository to return a valid stripe info
    mock_repo = mocker.patch(
        "simcore_service_webserver.products._service.ProductRepository.create_from_app"
    )

    # Test when stripe info is returned successfully
    expected_stripe_info = ProductStripeInfoGet(
        stripe_price_id="price_id", stripe_tax_rate_id="tax_id"
    )

    async def _mock(*args, **kw):
        return expected_stripe_info

    mock_repo.return_value.get_product_stripe_info_or_none.side_effect = _mock

    stripe_info = await products_service.get_product_stripe_info(
        app, product_name=default_product_name
    )
    assert stripe_info == expected_stripe_info


async def test_get_template_content(app: web.Application):
    template_name = "some_template"
    with pytest.raises(ProductTemplateNotFoundError):
        await _service.get_template_content(app, template_name=template_name)


async def test_auto_create_products_groups(app: web.Application):
    groups = await _service.auto_create_products_groups(app)
    assert isinstance(groups, dict)

    assert all(
        group_id is not None for group_id in groups.values()
    ), f"Invalid {groups}"
