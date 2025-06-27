# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from collections.abc import Iterator
from decimal import Decimal
from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedByServiceGet,
    OsparcCreditsAggregatedUsagesPage,
)
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.models import UserRole

_SERVICE_RUN_GET = OsparcCreditsAggregatedUsagesPage(
    items=[
        OsparcCreditsAggregatedByServiceGet(
            osparc_credits=Decimal(-50),
            service_key="simcore/services/comp/itis/sleeper",
            running_time_in_hours=Decimal(0.5),
        )
    ],
    total=1,
)


@pytest.fixture
def mock_get_osparc_credits_aggregated_usages_page(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_service.service_runs.get_osparc_credits_aggregated_usages_page",
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
async def test_export_service_usage_redirection(
    client: TestClient,
    logged_user: UserInfoDict,
    setup_wallets_db,
    mock_get_osparc_credits_aggregated_usages_page,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app
    url = (
        client.app.router["list_osparc_credits_aggregated_usages"]
        .url_for()
        .with_query(
            wallet_id=f"{setup_wallets_db}",
            aggregated_by="services",
            time_period=1,
        )
    )
    resp = await client.get(f"{url}")
    assert resp.status == expected

    if resp.status == status.HTTP_200_OK:
        assert mock_get_osparc_credits_aggregated_usages_page.called
