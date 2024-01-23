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
from models_library.resource_tracker import ServiceResourceUsagesFilters
from models_library.rest_ordering import OrderBy
from pydantic import AnyUrl, parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
def mock_export_usage_services(mocker: MockerFixture) -> tuple:
    mock_export_usage = mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_api.service_runs.export_service_runs",
        spec=True,
        return_value=parse_obj_as(AnyUrl, "https://www.google.com/"),
    )
    return mock_export_usage


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


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
        (UserRole.PRODUCT_OWNER, web.HTTPOk),
        (UserRole.ADMIN, web.HTTPOk),
    ],
)
async def test_export_service_usage_redirection(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_export_usage_services,
    user_role: UserRole,
    expected: type[web.HTTPException],
):
    url = client.app.router["export_resource_usage_services"].url_for()
    resp = await client.get(f"{url}")
    assert resp.status == expected.status_code

    if resp.status == web.HTTPOk:
        # checks is a redirection
        assert len(resp.history) == 1
        assert resp.history[0].status == web.HTTPFound.status_code

        assert mock_export_usage_services.called


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_export_usage_services,
):
    # export service usage with filters and ordering
    _order_by = {"field": "started_at", "direction": "desc"}
    _filter = {"started_at": {"from": "2023-12-01", "until": "2024-01-01"}}
    url = (
        client.app.router["export_resource_usage_services"]
        .url_for()
        .with_query(
            wallet_id=f"{setup_wallets_db}",
            filters=json.dumps(_filter),
            order_by=json.dumps(_order_by),
        )
    )
    resp = await client.get(f"{url}")

    # checks is a redirection
    assert len(resp.history) == 1
    assert resp.history[0].status == web.HTTPFound.status_code

    assert mock_export_usage_services.called
    args = mock_export_usage_services.call_args[1]

    assert args["order_by"] == parse_obj_as(OrderBy, _order_by)
    assert args["filters"] == parse_obj_as(ServiceResourceUsagesFilters, _filter)
