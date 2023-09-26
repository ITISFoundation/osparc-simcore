import asyncio
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_pricing_details import (
    resource_tracker_pricing_details,
)
from simcore_postgres_database.models.resource_tracker_pricing_plan_to_service import (
    resource_tracker_pricing_plan_to_service,
)
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)
from simcore_service_resource_usage_tracker.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)
from simcore_service_resource_usage_tracker.resource_tracker_process_messages import (
    _process_heartbeat_event,
    _process_start_event,
    _process_stop_event,
)

from .conftest import assert_credit_transactions_db_row

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
                cost_per_unit=Decimal(1500),
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=True,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="M",
                cost_per_unit=Decimal(1500),
                valid_from=datetime.now(tz=timezone.utc),
            ),
            simcore_default=False,
            specific_info={},
        )
        con.execute(
            resource_tracker_pricing_details.insert().values(
                pricing_plan_id=1,
                unit_name="L",
                cost_per_unit=Decimal(1500),
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
        con.execute(resource_tracker_credit_transactions.delete())


async def test_process_event_functions(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db,
    resource_tracker_pricing_tables_db,
    initialized_app,
):
    engine = initialized_app.state.engine
    publisher = rabbitmq_client("publisher")

    msg = random_rabbit_message_start(
        wallet_id=1, wallet_name="test", pricing_plan_id=1, pricing_detail_id=1
    )
    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )
    await _process_start_event(resource_tacker_repo, msg, publisher)
    output = await assert_credit_transactions_db_row(postgres_db, msg.service_run_id)
    assert output[8] == 0.0
    assert output[9] == "PENDING"
    assert output[10] == "DEDUCT_SERVICE_RUN"
    first_occurence_of_last_heartbeat_at = output[14]
    modified_at = output[15]

    await asyncio.sleep(0)
    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await _process_heartbeat_event(resource_tacker_repo, heartbeat_msg, publisher)
    output = await assert_credit_transactions_db_row(
        postgres_db, msg.service_run_id, modified_at
    )
    first_credits_used = output[8]
    assert first_credits_used < 0.0
    assert output[9] == "PENDING"
    assert first_occurence_of_last_heartbeat_at < output[14]
    modified_at = output[15]

    await asyncio.sleep(
        2
    )  # NOTE: Computation of credits depends on time ((stop-start)*cost_per_unit)
    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await _process_stop_event(resource_tacker_repo, stopped_msg, publisher)
    output = await assert_credit_transactions_db_row(
        postgres_db, msg.service_run_id, modified_at
    )
    assert output[8] < first_credits_used
    assert output[9] == "BILLED"
