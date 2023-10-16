# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import operator
from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.product import GetProduct
from models_library.products import ProductName
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver._constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.db.models import UserRole


@pytest.fixture(params=["osparc", "tis", "s4l"])
def product_name(request: pytest.FixtureRequest) -> ProductName:
    return request.param


def product_price(
    all_product_prices: dict[ProductName, Decimal],
    product_name: ProductName,
) -> Decimal:
    return all_product_prices[product_name]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        *((role, web.HTTPOk) for role in UserRole if role >= UserRole.USER),
    ],
)
async def test_get_product_price_when_undefined(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: type[web.HTTPException],
    latest_osparc_price: Decimal,
):
    response = await client.get("/v0/credits-price")
    data, error = await assert_status(response, expected)

    if not error:
        assert data["usdPerCredit"] == latest_osparc_price


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPForbidden),
        (UserRole.PRODUCT_OWNER, web.HTTPOk),
        (UserRole.ADMIN, web.HTTPForbidden),
    ],
)
async def test_get_product_access_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: type[web.HTTPException],
    latest_osparc_price: Decimal,
):
    response = await client.get("/v0/products/current")
    data, error = await assert_status(response, expected)
    assert operator.xor(data is None, error is None)


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.PRODUCT_OWNER)],
)
async def test_get_product(
    product_name: ProductName,
    product_price: Decimal,
    logged_user: UserInfoDict,
    client: TestClient,
):
    # TODO: create client that adds headers from start
    headers = {X_PRODUCT_NAME_HEADER: product_name}

    response = await client.get("/v0/products/current", headers=headers)
    data, error = await assert_status(response, web.HTTPOk)

    got_product = GetProduct(**data)
    assert got_product.name == product_name
    assert got_product.credits_per_usd == (
        Decimal(1) / product_price if product_price else None
    )
    assert not error

    response = await client.get(f"/v0/products/{product_name}", headers=headers)
    data, error = await assert_status(response, web.HTTPOk)
    assert got_product == GetProduct(**data)
    assert not error

    response = await client.get("/v0/product/invalid", headers=headers)
    data, error = await assert_status(response, web.HTTPNotFound)
    assert not data
    assert error
