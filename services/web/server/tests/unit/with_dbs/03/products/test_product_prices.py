# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


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
    client: TestClient, expected: type[web.HTTPException], logged_user: UserInfoDict
):
    response = await client.get("/v0/price")
    data, error = await assert_status(response, expected)

    if not error:
        assert data["dollarsPerCredit"] == 0


async def test_it():
    # osparc 1
    # foo 2
    # bar 3
    # osparc 2
    # foo 1
    assert False

    # test adding negative price raise exceptio in the database
    #

    # Separate PR to introduce POs
    #
    # ONLY for POs
    # /product
    # as a section with price that includes all values
    #
    # check that authorization by PRODUCT_OWNER user
    #

    # tests create payment with defined/undefined price
