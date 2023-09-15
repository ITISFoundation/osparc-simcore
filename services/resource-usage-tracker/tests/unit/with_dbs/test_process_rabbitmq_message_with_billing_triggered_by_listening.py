import asyncio
from datetime import datetime, timezone
from typing import Callable, Iterator

import pytest
import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingBaseMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.resource_tracker_pricing_details import (
    resource_tracker_pricing_details,
)
from simcore_postgres_database.models.resource_tracker_pricing_plan_to_service import (
    resource_tracker_pricing_plan_to_service,
)
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)

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
                cost_per_unit=500,
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=True,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="M",
                cost_per_unit=1000,
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=False,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="L",
                cost_per_unit=1500,
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


@pytest.mark.testit
async def test_process_events_via_rabbit(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    initialized_app,
    resource_tracker_service_run_db,
    resource_tracker_pricing_tables_db,
):
    publisher = rabbitmq_client("publisher")
    msg = random_rabbit_message_start(
        wallet_id=1, wallet_name="what ever", pricing_plan_id=1, pricing_detail_id=1
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
