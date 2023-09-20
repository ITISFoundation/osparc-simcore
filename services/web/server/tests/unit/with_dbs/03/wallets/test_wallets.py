# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from collections.abc import AsyncIterator
from decimal import Decimal
from unittest import mock

import arrow
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, UserInfoDict
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def mock_rut_sum_total_available_credits_in_the_wallet(
    mocker: MockerFixture,
) -> mock.Mock:
    return mocker.patch(
        "simcore_service_webserver.wallets._api.get_wallet_total_available_credits",
        return_value=WalletTotalCredits(
            wallet_id=1, available_osparc_credits=Decimal(10.2)
        ),
    )


@pytest.mark.testit
@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_wallets_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: type[web.HTTPException],
    wallets_clean_db: AsyncIterator[None],
    mock_rut_sum_total_available_credits_in_the_wallet: mock.Mock,
):
    assert client.app

    # list user wallets
    url = client.app.router["list_wallets"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data == []

    # create a new wallet
    url = client.app.router["create_wallet"].url_for()
    resp = await client.post(
        f"{url}", json={"name": "My first wallet", "description": "Custom description"}
    )
    added_wallet, _ = await assert_status(resp, web.HTTPCreated)

    # list user wallets
    url = client.app.router["list_wallets"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert len(data) == 1
    assert data[0]["walletId"] == added_wallet["walletId"]
    assert data[0]["name"] == "My first wallet"
    assert data[0]["description"] == "Custom description"
    assert data[0]["thumbnail"] is None
    assert data[0]["status"] == "ACTIVE"
    assert data[0]["availableCredits"] == float(
        mock_rut_sum_total_available_credits_in_the_wallet.return_value.available_osparc_credits
    )
    store_modified_field = arrow.get(data[0]["modified"])

    # update user wallet
    url = client.app.router["update_wallet"].url_for(
        wallet_id=f"{added_wallet['walletId']}"
    )
    resp = await client.put(
        f"{url}",
        json={
            "name": "My first wallet",
            "description": None,
            "thumbnail": "New thumbnail",
            "status": "INACTIVE",
        },
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data["walletId"] == added_wallet["walletId"]
    assert data["name"] == "My first wallet"
    assert data["description"] is None
    assert data["thumbnail"] == "New thumbnail"
    assert data["status"] == "INACTIVE"
    assert arrow.get(data["modified"]) > store_modified_field

    # list user wallets and check the updated wallet
    url = client.app.router["list_wallets"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert len(data) == 1
    assert data[0]["walletId"] == added_wallet["walletId"]
    assert data[0]["name"] == "My first wallet"
    assert data[0]["description"] is None
    assert data[0]["thumbnail"] == "New thumbnail"
    assert data[0]["status"] == "INACTIVE"
    assert arrow.get(data[0]["modified"]) > store_modified_field

    # add two more wallets
    url = client.app.router["create_wallet"].url_for()
    resp = await client.post(f"{url}", json={"name": "My second wallet"})
    await assert_status(resp, web.HTTPCreated)
    resp = await client.post(
        f"{url}",
        json={
            "name": "My third wallet",
            "description": "Custom description",
            "thumbnail": "Custom thumbnail",
        },
    )
    await assert_status(resp, web.HTTPCreated)

    # list user wallets
    url = client.app.router["list_wallets"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert len(data) == 3

    # Now we will log as a different user
    async with LoggedUser(client):
        # User who does not have access will try to access the wallet
        url = client.app.router["update_wallet"].url_for(
            wallet_id=f"{added_wallet['walletId']}"
        )
        resp = await client.put(
            f"{url}",
            json={
                "name": "I dont have permisions to change this wallet",
                "description": "-",
                "thumbnail": "-",
                "status": "ACTIVE",
            },
        )
        _, errors = await assert_status(
            resp,
            web.HTTPForbidden,
        )
        assert errors
