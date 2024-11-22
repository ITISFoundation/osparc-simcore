# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import json
from collections.abc import Iterator
from http import HTTPStatus
from typing import cast

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunGet,
    ServiceRunPage,
)
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.models import UserRole

_SERVICE_RUN_GET = ServiceRunPage(
    items=[
        ServiceRunGet.model_validate(
            {
                "service_run_id": "comp_1_5c2110be-441b-11ee-a0e8-02420a000040_1",
                "wallet_id": 1,
                "wallet_name": "the super wallet!",
                "user_id": 1,
                "user_email": "name@email.testing",
                "project_id": "5c2110be-441b-11ee-a0e8-02420a000040",
                "project_name": "osparc",
                "project_tags": [],
                "node_id": "3d2133f4-aba4-4364-9f7a-9377dea1221f",
                "node_name": "sleeper",
                "root_parent_project_id": "5c2110be-441b-11ee-a0e8-02420a000040",
                "root_parent_project_name": "osparc",
                "service_key": "simcore/services/comp/itis/sleeper",
                "service_version": "2.0.2",
                "service_type": "DYNAMIC_SERVICE",
                "started_at": "2023-08-26T14:18:17.600493+00:00",
                "stopped_at": "2023-08-26T14:18:19.358355+00:00",
                "service_run_status": "SUCCESS",
                "credit_cost": None,
                "transaction_status": None,
            }
        )
    ],
    total=1,
)


@pytest.fixture
def mock_list_usage_services(mocker: MockerFixture) -> tuple:
    return mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_api.service_runs.get_service_run_page",
        spec=True,
        return_value=_SERVICE_RUN_GET,
    )


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
        assert row

        yield cast(int, row[0])

        con.execute(wallets.delete())


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_list_service_usage_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_list_usage_services,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app
    url = client.app.router["list_resource_usage_services"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_list_usage_services,
):
    # list service usage without wallets
    assert client.app
    url = client.app.router["list_resource_usage_services"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.call_count == 1

    # list service usage with wallets as "accountant"
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(wallet_id=f"{setup_wallets_db}")
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.call_count == 2
    assert mock_list_usage_services.call_args[1]["access_all_wallet_usage"] is True

    # Remove "write" permission on the wallet
    url = client.app.router["update_wallet_group"].url_for(
        wallet_id=f"{setup_wallets_db}",
        group_id=f"{logged_user['primary_gid']}",
    )
    resp = await client.put(
        f"{url}", json={"read": True, "write": False, "delete": False}
    )
    await assert_status(resp, status.HTTP_200_OK)

    # list service usage with wallets as "basic" user
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(wallet_id=f"{setup_wallets_db}")
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.call_count == 3
    assert mock_list_usage_services.call_args[1]["access_all_wallet_usage"] is False


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage_with_order_by_query_param(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_list_usage_services,
):
    assert client.app

    # without any additional query parameter
    url = client.app.router["list_resource_usage_services"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.called

    # with order by query parameter
    _filter = {"field": "started_at", "direction": "desc"}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.called

    # with order by query parameter
    _filter = {"field": "started_at", "direction": "asc"}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.called

    # with non-supported field in order by query parameter
    _filter = {"field": "non-supported", "direction": "desc"}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert mock_list_usage_services.called
    assert error["status"] == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error["errors"][0]["message"].startswith(
        "Value error, We do not support ordering by provided field"
    )

    # with non-parsable field in order by query parameter
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=",invalid json")
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert mock_list_usage_services.called
    assert error["status"] == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid JSON" in error["errors"][0]["message"]

    # with order by without direction
    _filter = {"field": "started_at"}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.called

    # with wrong direction
    _filter = {"field": "non-supported", "direction": "wrong"}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert mock_list_usage_services.called
    assert error["status"] == status.HTTP_422_UNPROCESSABLE_ENTITY

    errors = {(e["code"], e["field"]) for e in error["errors"]}
    assert {
        ("value_error", "order_by.field"),
        ("enum", "order_by.direction"),
    } == errors
    assert len(errors) == 2

    # without field
    _filter = {"direction": "asc"}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(order_by=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert mock_list_usage_services.called
    assert error["status"] == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error["errors"][0]["message"].startswith("Field required")
    assert error["errors"][0]["code"] == "missing"
    assert error["errors"][0]["field"] == "order_by.field"


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage_with_filters_query_param(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_list_usage_services,
):
    assert client.app

    # with unable to decode filter query parameter
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(filters='{"test"}')
    )
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert error["status"] == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error["errors"][0]["message"].startswith("Invalid JSON")

    # with correct filter query parameter
    _filter = {"started_at": {"from": "2023-12-01", "until": "2024-01-01"}}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(filters=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
    assert mock_list_usage_services.called

    # with only one started_at filter query parameter
    _filter = {"started_at": {"until": "2023-12-02"}}
    url = (
        client.app.router["list_resource_usage_services"]
        .url_for()
        .with_query(filters=json.dumps(_filter))
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)
