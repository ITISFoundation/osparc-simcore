# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from decimal import Decimal
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_purchases as rut_licensed_items_purchases,
)
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole

_LICENSED_ITEM_PURCHASE_GET = (
    rut_licensed_items_purchases.LicensedItemPurchaseGet.model_validate(
        {
            "licensed_item_purchase_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
            "product_name": "osparc",
            "licensed_item_id": "303942ef-6d31-4ba8-afbe-dbb1fce2a953",
            "key": "Duke",
            "version": "1.0.0",
            "wallet_id": 1,
            "wallet_name": "My Wallet",
            "pricing_unit_cost_id": 1,
            "pricing_unit_cost": Decimal(10),
            "start_at": "2023-01-11 13:11:47.293595",
            "expire_at": "2023-01-11 13:11:47.293595",
            "num_of_seats": 1,
            "purchased_by_user": 1,
            "user_email": "test@test.com",
            "purchased_at": "2023-01-11 13:11:47.293595",
            "modified": "2023-01-11 13:11:47.293595",
        }
    )
)

_LICENSED_ITEM_PURCHASE_PAGE = rut_licensed_items_purchases.LicensedItemsPurchasesPage(
    items=[_LICENSED_ITEM_PURCHASE_GET],
    total=1,
)


@pytest.fixture
def mock_get_licensed_items_purchases_page(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_purchases_service.licensed_items_purchases.get_licensed_items_purchases_page",
        spec=True,
        return_value=_LICENSED_ITEM_PURCHASE_PAGE,
    )


@pytest.fixture
def mock_get_licensed_item_purchase(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_purchases_service.licensed_items_purchases.get_licensed_item_purchase",
        spec=True,
        return_value=_LICENSED_ITEM_PURCHASE_GET,
    )


@pytest.fixture
def mock_get_wallet_by_user(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.licenses._licensed_items_purchases_service.get_wallet_by_user",
        spec=True,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_licensed_items_purchaches_handlers(
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
