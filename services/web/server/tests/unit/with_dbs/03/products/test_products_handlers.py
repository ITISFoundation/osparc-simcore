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
from simcore_postgres_database.constants import QUANTIZE_EXP_ARG
from simcore_service_webserver._constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.db.models import UserRole


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


@pytest.fixture(params=["osparc", "tis", "s4l"])
def product_name(request: pytest.FixtureRequest) -> ProductName:
    return request.param


@pytest.fixture
def expected_credits_per_usd(
    all_product_prices: dict[ProductName, Decimal],
    product_name: ProductName,
) -> Decimal | None:
    if usd_per_credit := all_product_prices[product_name]:
        return Decimal(1 / usd_per_credit).quantize(QUANTIZE_EXP_ARG)
    return None


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.PRODUCT_OWNER)],
)
async def test_get_product(
    product_name: ProductName,
    expected_credits_per_usd: Decimal | None,
    logged_user: UserInfoDict,
    client: TestClient,
):
    current_project_headers = {X_PRODUCT_NAME_HEADER: product_name}
    response = await client.get("/v0/products/current", headers=current_project_headers)
    data, error = await assert_status(response, web.HTTPOk)

    got_product = GetProduct(**data)
    assert got_product.name == product_name
    assert got_product.credits_per_usd == expected_credits_per_usd
    assert not error

    response = await client.get(f"/v0/products/{product_name}")
    data, error = await assert_status(response, web.HTTPOk)
    assert got_product == GetProduct(**data)
    assert not error

    response = await client.get("/v0/product/invalid")
    data, error = await assert_status(response, web.HTTPNotFound)
    assert not data
    assert error
