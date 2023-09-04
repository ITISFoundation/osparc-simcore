from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.resource_tracker_pricing_details import (
    resource_tracker_pricing_details,
)
from simcore_postgres_database.models.resource_tracker_pricing_plan_to_service import (
    resource_tracker_pricing_plan_to_service,
)
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def resource_tracker_pricing_tables_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        con.execute(
            resource_tracker_pricing_plans.insert().values(
                product_name="osparc",
                name="test_name",
                description="",
                classification="TIER",
                is_active=True,
            )
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="S",
                cost_per_unit=Decimal(5),
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=True,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="M",
                cost_per_unit=Decimal(15.6),
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=False,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="L",
                cost_per_unit=Decimal(28.9),
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=False,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_plan_to_service.insert().values(
                pricing_plan_id=1,
                product="osparc",
                service_key="simcore/services/comp/itis/sleeper",
                service_version="1.0.16",
            )
        )

        yield

        con.execute(resource_tracker_pricing_plan_to_service.delete())
        con.execute(resource_tracker_pricing_details.delete())
        con.execute(resource_tracker_pricing_plans.delete())


async def test_pricing_plans_get(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    postgres_db: sa.engine.Engine,
    resource_tracker_pricing_tables_db: None,
    async_client: httpx.AsyncClient,
):
    url = URL("/v1/pricing-plans")

    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert len(data[0]["details"]) == 3

    response = await async_client.get(
        f'{url.with_query({"product_name": "osparc", "service_key": "simcore/services/comp/itis/sleeper", "service_version": "1.0.16"})}'
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert len(data[0]["details"]) == 3
