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
        (role, web.HTTPOk if role >= UserRole.USER else web.HTTPForbidden)
        for role in UserRole
    ],
)
async def test_get_product_prize(client: TestClient, logged_user: UserInfoDict):
    response = await client.get("/v0/price")
    data, _ = await assert_status(response, web.HTTPOk)

    assert data["dollarsPerCredit"] >= 0
