from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.resource_tracker_pricing_plan_to_service import (
    resource_tracker_pricing_plan_to_service,
)
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)
from simcore_postgres_database.models.resource_tracker_pricing_unit_costs import (
    resource_tracker_pricing_unit_costs,
)
from simcore_postgres_database.models.resource_tracker_pricing_units import (
    resource_tracker_pricing_units,
)
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_SERVICE_KEY = "simcore/services/comp/itis/sleeper"
_SERVICE_VERSION = "1.0.16"
_PRICING_PLAN_ID = 1


@pytest.fixture()
def resource_tracker_pricing_tables_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        con.execute(
            resource_tracker_pricing_plans.insert().values(
                product_name="osparc",
                display_name="ISolve Thermal",
                description="",
                classification="TIER",
                is_active=True,
                pricing_plan_key="isolve-thermal",
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                unit_name="S",
                default=False,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            ),
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=1,
                pricing_unit_name="S",
                cost_per_unit=Decimal(5),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=None,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                unit_name="M",
                default=True,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            ),
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=2,
                pricing_unit_name="M",
                cost_per_unit=Decimal(15.6),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=None,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                unit_name="L",
                default=False,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            ),
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=3,
                pricing_unit_name="L",
                cost_per_unit=Decimal(17.7),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=datetime.now(tz=timezone.utc),
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=3,
                pricing_unit_name="L",
                cost_per_unit=Decimal(28.9),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=None,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_plan_to_service.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                service_key=_SERVICE_KEY,
                service_version=_SERVICE_VERSION,
                service_default_plan=True,
            )
        )

        yield

        con.execute(resource_tracker_pricing_plan_to_service.delete())
        con.execute(resource_tracker_pricing_units.delete())
        con.execute(resource_tracker_pricing_plans.delete())
        con.execute(resource_tracker_pricing_unit_costs.delete())


async def test_get_default_pricing_plan_for_service(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    postgres_db: sa.engine.Engine,
    resource_tracker_pricing_tables_db: None,
    async_client: httpx.AsyncClient,
):
    url = URL(f"/v1/services/{_SERVICE_KEY}/{_SERVICE_VERSION}/pricing-plan")
    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    assert len(data["pricing_units"]) == 3
    assert data["pricing_units"][0]["unit_name"] == "S"
    assert data["pricing_units"][1]["unit_name"] == "M"
    assert data["pricing_units"][2]["unit_name"] == "L"

    _PRICING_UNIT_ID = 2
    url = URL(f"/v1/pricing-plans/{_PRICING_PLAN_ID}/pricing-units/{_PRICING_UNIT_ID}")
    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    assert data["pricing_unit_id"] == _PRICING_UNIT_ID
