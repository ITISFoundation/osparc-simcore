# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_checkouts as rut_licensed_items_checkouts,
)
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole

_LICENSED_ITEM_CHECKOUT_GET = (
    rut_licensed_items_checkouts.LicensedItemCheckoutGet.model_validate({})
)

_LICENSED_ITEM_CHECKOUT_PAGE = rut_licensed_items_checkouts.LicensedItemsCheckoutsPage(
    items=[_LICENSED_ITEM_CHECKOUT_GET],
    total=1,
)


@pytest.fixture
def mock_get_licensed_items_purchases_page(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_api.licensed_items_checkouts_api.get_licensed_items_purchases_page",
        spec=True,
        return_value=_LICENSED_ITEM_CHECKOUT_PAGE,
    )


@pytest.fixture
def mock_get_licensed_item_purchase(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_api.licensed_items_purchases.get_licensed_item_purchase",
        spec=True,
        return_value=_LICENSED_ITEM_CHECKOUT_GET,
    )


@pytest.fixture
def mock_get_wallet_by_user(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_checkouts_api.get_wallet_by_user",
        spec=True,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_licensed_items_checkouts_handlers(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    mock_get_licensed_items_purchases_page: MockerFixture,
    mock_get_licensed_item_purchase: MockerFixture,
    mock_get_wallet_by_user: MockerFixture,
):
    assert client.app

    # list
    url = client.app.router["list_wallet_licensed_items_purchases"].url_for(
        wallet_id="1"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert LicensedItemPurchaseGet(**data[0])

    # get
    url = client.app.router["get_licensed_item_purchase"].url_for(
        licensed_item_purchase_id=f"{_LICENSED_ITEM_PURCHASE_PAGE.items[0].licensed_item_purchase_id}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert LicensedItemPurchaseGet(**data)
