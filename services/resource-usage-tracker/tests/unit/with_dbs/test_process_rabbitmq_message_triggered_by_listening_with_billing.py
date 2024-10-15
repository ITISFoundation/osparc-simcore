import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Iterator

import pytest
import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingBaseMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.resource_tracker import UnitExtraInfo
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
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

from .conftest import assert_service_runs_db_row

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
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
                display_name="ISolve Thermal",
                description="",
                classification="TIER",
                is_active=True,
                pricing_plan_key="isolve-thermal",
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=1,
                unit_name="S",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
                default=False,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=1,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=1,
                pricing_unit_name="S",
                cost_per_unit=Decimal(500),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=None,
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=1,
                unit_name="M",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
                default=True,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=1,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=2,
                pricing_unit_name="M",
                cost_per_unit=Decimal(1000),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=None,
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_units.insert().values(
                pricing_plan_id=1,
                unit_name="L",
                unit_extra_info=UnitExtraInfo.model_config["json_schema_extra"][
                    "examples"
                ][0],
                default=False,
                specific_info={},
                created=datetime.now(tz=timezone.utc),
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            resource_tracker_pricing_unit_costs.insert().values(
                pricing_plan_id=1,
                pricing_plan_key="isolve-thermal",
                pricing_unit_id=3,
                pricing_unit_name="L",
                cost_per_unit=Decimal(1500),
                valid_from=datetime.now(tz=timezone.utc),
                valid_to=None,
                created=datetime.now(tz=timezone.utc),
                comment="",
                modified=datetime.now(tz=timezone.utc),
            )
        )
        con.execute(
            services_meta_data.insert().values(
                key="simcore/services/comp/itis/sleeper",
                version="1.0.16",
                name="name",
                description="description",
            )
        )
        con.execute(
            resource_tracker_pricing_plan_to_service.insert().values(
                pricing_plan_id=1,
                service_key="simcore/services/comp/itis/sleeper",
                service_version="1.0.16",
                service_default_plan=True,
            )
        )

        yield

        con.execute(resource_tracker_pricing_plan_to_service.delete())
        con.execute(resource_tracker_pricing_units.delete())
        con.execute(resource_tracker_pricing_plans.delete())
        con.execute(resource_tracker_pricing_unit_costs.delete())
        con.execute(resource_tracker_credit_transactions.delete())
        con.execute(services_meta_data.delete())


@pytest.mark.flaky(max_runs=3)
async def test_process_events_via_rabbit(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    initialized_app,
    resource_tracker_service_run_db,
    resource_tracker_pricing_tables_db,
):
    publisher = create_rabbitmq_client("publisher")
    msg = random_rabbit_message_start(
        wallet_id=1,
        wallet_name="what ever",
        pricing_plan_id=1,
        pricing_unit_id=1,
        pricing_unit_cost_id=1,
    )
    await publisher.publish(RabbitResourceTrackingBaseMessage.get_channel_name(), msg)
    await asyncio.sleep(3)
    await assert_service_runs_db_row(postgres_db, msg.service_run_id, "RUNNING")

    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), heartbeat_msg
    )
    await assert_service_runs_db_row(postgres_db, msg.service_run_id, "RUNNING")

    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), stopped_msg
    )
    await assert_service_runs_db_row(postgres_db, msg.service_run_id, "SUCCESS")
