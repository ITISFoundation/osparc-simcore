# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import operator
from decimal import Decimal
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.products import ProductGet, ProductUIGet
from models_library.products import ProductName
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from servicelib.status_codes_utils import is_2xx_success
from simcore_postgres_database.constants import QUANTIZE_EXP_ARG
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.groups.api import auto_add_user_to_product_group


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        *((_, status.HTTP_200_OK) for _ in UserRole if _ >= UserRole.USER),
    ],
)
async def test_get_product_price_when_undefined(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    latest_osparc_price: Decimal,
):
    response = await client.get("/v0/credits-price")
    data, error = await assert_status(response, expected)

    if not error:
        assert data["usdPerCredit"] == latest_osparc_price


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_get_product_access_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
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
    [UserRole.PRODUCT_OWNER],
)
async def test_get_product(
    product_name: ProductName,
    expected_credits_per_usd: Decimal | None,
    logged_user: UserInfoDict,
    client: TestClient,
):
    # give access to user to this product
    assert client.app
    await auto_add_user_to_product_group(
        client.app, user_id=logged_user["id"], product_name=product_name
    )

    current_product_headers = {X_PRODUCT_NAME_HEADER: product_name}
    response = await client.get("/v0/products/current", headers=current_product_headers)
    data, error = await assert_status(response, status.HTTP_200_OK)

    got_product = ProductGet(**data)
    assert got_product.name == product_name
    assert got_product.credits_per_usd == expected_credits_per_usd
    assert not error

    response = await client.get(f"/v0/products/{product_name}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert got_product == ProductGet(**data)
    assert not error

    response = await client.get("/v0/products/invalid")
    data, error = await assert_status(response, status.HTTP_404_NOT_FOUND)
    assert not data
    assert error


@pytest.mark.parametrize(
    "user_role, expected_status_code",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_get_current_product_ui(
    app_products_names: list[ProductName],
    product_name: ProductName,
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    expected_status_code: int,
):
    assert logged_user["role"] == user_role
    assert product_name in app_products_names

    # give access to user to this product
    assert client.app
    await auto_add_user_to_product_group(
        client.app, user_id=logged_user["id"], product_name=product_name
    )

    assert (
        client.app.router["get_current_product_ui"].url_for().path
        == "/v0/products/current/ui"
    )
    response = await client.get(
        "/v0/products/current/ui", headers={X_PRODUCT_NAME_HEADER: product_name}
    )

    data, error = await assert_status(response, expected_status_code)

    if is_2xx_success(expected_status_code):
        # ui is something owned and fully controlled by the front-end
        # Will be something like the data stored in this file
        # https://github.com/itisfoundation/osparc-simcore/blob/1dcd369717959348099cc6241822a1f0aff0382c/services/static-webserver/client/source/resource/osparc/new_studies.json
        assert not error
        assert data

        product_ui = ProductUIGet.model_validate(data)
        assert product_ui.product_name == product_name
    else:
        assert error
        assert not data
