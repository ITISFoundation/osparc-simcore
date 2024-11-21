# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from models_library.resource_tracker import UnitExtraInfo
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
from simcore_postgres_database.models.services import services_meta_data
from starlette import status
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_SERVICE_KEY = "simcore/services/comp/itis/isolve"
_SERVICE_VERSION = "1.0.16"
_PRICING_PLAN_ID = 1

_PRICING_UNIT_ID = 2

_SERVICE_KEY_2 = "simcore/services/comp/itis/sleeper"
_SERVICE_VERSION_2 = "2.10.1"
_PRICING_PLAN_ID_2 = 2


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
            resource_tracker_pricing_plans.insert().values(
                product_name="osparc",
                display_name="Sleeper",
                description="",
                classification="TIER",
                is_active=True,
                pricing_plan_key="sleeper",
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                unit_name="S",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
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
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                unit_name="M",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
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
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID,
                unit_name="L",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
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
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID_2,
                unit_name="XXL",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
                default=True,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            ),
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID_2,
                pricing_plan_key="sleeper",
                pricing_unit_id=4,
                pricing_unit_name="XXL",
                cost_per_unit=Decimal(68),
                valid_from=datetime.now(tz=timezone.utc),
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )

        con.execute(
            services_meta_data.insert().values(
                key=_SERVICE_KEY,
                version=_SERVICE_VERSION,
                name="name",
                description="description",
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

        con.execute(
            services_meta_data.insert().values(
                key=_SERVICE_KEY_2,
                version=_SERVICE_VERSION_2,
                name="name",
                description="description",
            )
        )
        con.execute(
            resource_tracker_pricing_plan_to_service.insert().values(
                pricing_plan_id=_PRICING_PLAN_ID_2,
                service_key=_SERVICE_KEY_2,
                service_version=_SERVICE_VERSION_2,
                service_default_plan=True,
            )
        )

        yield

        con.execute(resource_tracker_pricing_plan_to_service.delete())
        con.execute(resource_tracker_pricing_units.delete())
        con.execute(resource_tracker_pricing_plans.delete())
        con.execute(resource_tracker_pricing_unit_costs.delete())
        con.execute(services_meta_data.delete())


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

    url = URL(f"/v1/pricing-plans/{_PRICING_PLAN_ID}/pricing-units/{_PRICING_UNIT_ID}")
    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    assert data["pricing_unit_id"] == _PRICING_UNIT_ID

    url = URL(f"/v1/services/{_SERVICE_KEY_2}/{_SERVICE_VERSION_2}/pricing-plan")
    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    assert len(data["pricing_units"]) == 1
    assert data["pricing_units"][0]["unit_name"] == "XXL"

    bigger_version = "3.10.5"
    url = URL(f"/v1/services/{_SERVICE_KEY_2}/{bigger_version}/pricing-plan")
    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    assert len(data["pricing_units"]) == 1
    assert data["pricing_units"][0]["unit_name"] == "XXL"

    smaller_verion = "1.0.0"
    url = URL(f"/v1/services/{_SERVICE_KEY_2}/{smaller_verion}/pricing-plan")
    response = await async_client.get(f'{url.with_query({"product_name": "osparc"})}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
