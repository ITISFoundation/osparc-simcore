# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
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
    new_osparc_price: Decimal,
):
    response = await client.get("/v0/credits-price")
    data, error = await assert_status(response, expected)

    if not error:
        assert data["usdPerCredit"] == new_osparc_price
