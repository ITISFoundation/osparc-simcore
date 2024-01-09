# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import json
from collections.abc import Iterator
from typing import cast

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.models import UserRole

_SERVICE_RUN_GET: dict = {
    "items": [
        {
            "service_run_id": "comp_1_5c2110be-441b-11ee-a0e8-02420a000040_1",
            "wallet_id": 1,
            "wallet_name": "the super wallet!",
            "user_id": 1,
            "project_id": "5c2110be-441b-11ee-a0e8-02420a000040",
            "project_name": "osparc",
            "node_id": "3d2133f4-aba4-4364-9f7a-9377dea1221f",
            "node_name": "sleeper",
            "service_key": "simcore/services/comp/itis/sleeper",
            "service_version": "2.0.2",
            "service_type": "DYNAMIC_SERVICE",
            "service_resources": {
                "container": {
                    "image": "simcore/services/comp/itis/sleeper:2.0.2",
                    "resources": {
                        "CPU": {"limit": 0.1, "reservation": 0.1},
                        "RAM": {"limit": 2147483648, "reservation": 2147483648},
                    },
                    "boot_modes": ["CPU"],
                }
            },
            "started_at": "2023-08-26T14:18:17.600493+00:00",
            "stopped_at": "2023-08-26T14:18:19.358355+00:00",
            "service_run_status": "SUCCESS",
        }
    ],
    "total": 1,
    "limit": 1,
    "offset": 0,
    "links": {
        "first": "/api/v1/users?limit=1&offset=0",
        "last": "/api/v1/users?limit=1&offset=0",
        "self": "/api/v1/users?limit=1&offset=0",
        "next": "/api/v1/users?limit=1&offset=0",
        "prev": "/api/v1/users?limit=1&offset=0",
    },
}


@pytest.fixture
def mock_list_usage_services(mocker: MockerFixture) -> tuple:
    mock_list_with_wallets = mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_api.resource_tracker_client.list_service_runs_by_user_and_product",
        spec=True,
        return_value=_SERVICE_RUN_GET,
    )
    mock_list_without_wallets = mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_api.resource_tracker_client.list_service_runs_by_user_and_product_and_wallet",
        spec=True,
        return_value=_SERVICE_RUN_GET,
    )
    return mock_list_with_wallets, mock_list_without_wallets


@pytest.fixture()
def setup_wallets_db(
    postgres_db: sa.engine.Engine, logged_user: UserInfoDict
) -> Iterator[int]:
    with postgres_db.connect() as con:
        result = con.execute(
            wallets.insert()
            .values(
                name="My wallet",
                owner=logged_user["primary_gid"],
                status="ACTIVE",
                product_name="osparc",
            )
            .returning(sa.literal_column("*"))
        )
        row = result.fetchone()
        yield cast(int, row[0])
        con.execute(wallets.delete())


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_list_usage_services,
):
    # list service usage without wallets
    url = client.app.router["list_resource_usage_services"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, web.HTTPOk)
    assert mock_list_usage_services[0].called

    # list service usage with wallets as "accountant"
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(wallet_id=f"{setup_wallets_db}")
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, web.HTTPOk)
    assert mock_list_usage_services[1].call_count == 1
    assert mock_list_usage_services[1].call_args[1]["access_all_wallet_usage"] is True

    # Remove "write" permission on the wallet
    url = client.app.router["update_wallet_group"].url_for(
        wallet_id=f"{setup_wallets_db}",
        group_id=f"{logged_user['primary_gid']}",
    )
    resp = await client.put(
        f"{url}", json={"read": True, "write": False, "delete": False}
    )
    await assert_status(resp, web.HTTPOk)

    # list service usage with wallets as "basic" user
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(wallet_id=f"{setup_wallets_db}")
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, web.HTTPOk)
    assert mock_list_usage_services[1].call_count == 2
    assert mock_list_usage_services[1].call_args[1]["access_all_wallet_usage"] is False


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage_with_special_query_params(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_list_usage_services,
):
    # without anything
    url = client.app.router["list_resource_usage_services"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, web.HTTPOk)
    assert mock_list_usage_services[0].called

    ### ADDING SORT BY
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by="started_at desc, stopped_at")
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, web.HTTPOk)
    assert mock_list_usage_services[0].called

    #### ADDING SORT BY WITH non-supported field
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by="non-supported desc, stopped_at")
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, web.HTTPUnprocessableEntity)
    assert mock_list_usage_services[0].called
    assert error["status"] == web.HTTPUnprocessableEntity.status_code
    assert error["errors"][0]["message"].startswith(
        "We do not support ordering by provided field"
    )

    #### ADDING SORT BY WITH non-parsable field
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=",non-supported desc, stopped_at")
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, web.HTTPUnprocessableEntity)
    assert mock_list_usage_services[0].called
    assert error["status"] == web.HTTPUnprocessableEntity.status_code
    assert error["errors"][0]["message"].startswith(
        "order_by parameter is not parsable"
    )

    #### ADDING SORT BY WITH unable to decode
    _filter = {"started_at": {"from": "2023-12-01", "until": "2024-01-01"}}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(filters='{"test"}')
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, web.HTTPUnprocessableEntity)
    assert mock_list_usage_services[0].called
    assert error["status"] == web.HTTPUnprocessableEntity.status_code
    assert error["errors"][0]["message"].startswith(
        "Unable to decode filters parameter"
    )

    #### ADDING SORT BY Correct
    _filter = {"started_at": {"from": "2023-12-01", "until": "2024-01-01"}}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(filters=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, web.HTTPOk)
    assert mock_list_usage_services[0].called

    #### ADDING SORT BY Correct
    _filter = {"started_at": {"from": "2023-12-01"}}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(filters=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, web.HTTPUnprocessableEntity)
    assert mock_list_usage_services[0].called
    assert error["status"] == web.HTTPUnprocessableEntity.status_code
    assert error["errors"][0]["message"].startswith(
        "Both 'from' and 'until' keys must be provided in proper format <yyyy-mm-dd>."
    )
