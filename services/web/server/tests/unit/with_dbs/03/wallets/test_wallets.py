# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator, Iterator

import arrow
import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, UserInfoDict
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture()
def wallets_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(wallets.delete())


@pytest.mark.testit
@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_wallets_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: type[web.HTTPException],
    wallets_clean_db: AsyncIterator[None],
):
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
    assert data[0]["wallet_id"] == added_wallet["wallet_id"]
    assert data[0]["name"] == "My first wallet"
    assert data[0]["description"] == "Custom description"
    assert data[0]["thumbnail"] == None
    assert data[0]["status"] == "ACTIVE"
    store_modified_field = arrow.get(data[0]["modified"])

    # update user wallet
    url = client.app.router["update_wallet"].url_for(
        wallet_id=f"{added_wallet['wallet_id']}"
    )
    resp = await client.put(
        f"{url}",
        json={
            "name": "My first wallet",
            "description": "New description",
            "thumbnail": "New thumbnail",
            "status": "INACTIVE",
        },
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data["wallet_id"] == added_wallet["wallet_id"]
    assert data["name"] == "My first wallet"
    assert data["description"] == "New description"
    assert data["thumbnail"] == "New thumbnail"
    assert data["status"] == "INACTIVE"
    assert arrow.get(data["modified"]) > store_modified_field

    # list user wallets and check the updated wallet
    url = client.app.router["list_wallets"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert len(data) == 1
    assert data[0]["wallet_id"] == added_wallet["wallet_id"]
    assert data[0]["name"] == "My first wallet"
    assert data[0]["description"] == "New description"
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
    async with LoggedUser(client) as new_logged_user:
        # User who does not have access will try to access the wallet
        url = client.app.router["update_wallet"].url_for(
            wallet_id=f"{added_wallet['wallet_id']}"
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
