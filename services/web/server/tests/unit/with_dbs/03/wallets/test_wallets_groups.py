# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_wallets_groups_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    wallets_clean_db: AsyncIterator[None],
):
    # create a new wallet
    url = client.app.router["create_wallet"].url_for()
    resp = await client.post(
        f"{url}", json={"name": "My first wallet", "description": "Custom description"}
    )
    added_wallet, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # check the default wallet permissions
    url = client.app.router["list_wallet_groups"].url_for(
        wallet_id=f"{added_wallet['walletId']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["gid"] == logged_user["primary_gid"]
    assert data[0]["read"] == True
    assert data[0]["write"] == True
    assert data[0]["delete"] == True

    async with NewUser(
        app=client.app,
    ) as new_user:
        # We add new user to the wallet
        url = client.app.router["create_wallet_group"].url_for(
            wallet_id=f"{added_wallet['walletId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.post(
            f"{url}", json={"read": True, "write": False, "delete": False}
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)

        # Check the wallet permissions of added user
        url = client.app.router["list_wallet_groups"].url_for(
            wallet_id=f"{added_wallet['walletId']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] == True
        assert data[1]["write"] == False
        assert data[1]["delete"] == False

        # Update the wallet permissions of the added user
        url = client.app.router["update_wallet_group"].url_for(
            wallet_id=f"{added_wallet['walletId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.put(
            f"{url}", json={"read": True, "write": True, "delete": False}
        )
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert data["gid"] == new_user["primary_gid"]
        assert data["read"] == True
        assert data["write"] == True
        assert data["delete"] == False

        # List the wallet groups
        url = client.app.router["list_wallet_groups"].url_for(
            wallet_id=f"{added_wallet['walletId']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] == True
        assert data[1]["write"] == True
        assert data[1]["delete"] == False

        # Delete the wallet group
        url = client.app.router["delete_wallet_group"].url_for(
            wallet_id=f"{added_wallet['walletId']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.delete(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # List the wallet groups
        url = client.app.router["list_wallet_groups"].url_for(
            wallet_id=f"{added_wallet['walletId']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
        assert data[0]["gid"] == logged_user["primary_gid"]
