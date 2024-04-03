import asyncio
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from decimal import Decimal
from unittest import mock

import pytest
import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
    WalletCreditsLimitReachedMessage,
)
from models_library.resource_tracker import UnitExtraInfo
from pytest_mock.plugin import MockerFixture
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
from simcore_service_resource_usage_tracker.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)
from simcore_service_resource_usage_tracker.resource_tracker_process_messages import (
    _process_heartbeat_event,
    _process_start_event,
    _process_stop_event,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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
                unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
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
                unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
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
                unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
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


@pytest.fixture
async def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock(return_value=True)


async def test_process_event_functions(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db,
    resource_tracker_pricing_tables_db,
    initialized_app,
    mocked_message_parser,
):
    engine = initialized_app.state.engine
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")
    await consumer.subscribe(
        WalletCreditsLimitReachedMessage.get_channel_name(),
        mocked_message_parser,
        topics=["#"],
    )

    msg = random_rabbit_message_start(
        wallet_id=1,
        wallet_name="test",
        pricing_plan_id=1,
        pricing_unit_id=1,
        pricing_unit_cost_id=1,
    )
    resource_tracker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )
    await _process_start_event(resource_tracker_repo, msg, publisher)
    output = await assert_credit_transactions_db_row(postgres_db, msg.service_run_id)
    assert output.osparc_credits == 0.0
    assert output.transaction_status == "PENDING"
    assert output.transaction_classification == "DEDUCT_SERVICE_RUN"
    first_occurence_of_last_heartbeat_at = output.last_heartbeat_at
    modified_at = output.modified

    await asyncio.sleep(0)
    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await _process_heartbeat_event(resource_tracker_repo, heartbeat_msg, publisher)
    output = await assert_credit_transactions_db_row(
        postgres_db, msg.service_run_id, modified_at
    )
    first_credits_used = output.osparc_credits
    assert first_credits_used < 0.0
    assert output.transaction_status == "PENDING"
    assert first_occurence_of_last_heartbeat_at < output.last_heartbeat_at
    modified_at = output.modified

    await asyncio.sleep(
        2
    )  # NOTE: Computation of credits depends on time ((stop-start)*cost_per_unit)
    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await _process_stop_event(resource_tracker_repo, stopped_msg, publisher)
    output = await assert_credit_transactions_db_row(
        postgres_db, msg.service_run_id, modified_at
    )
    assert output.osparc_credits < first_credits_used
    assert output.transaction_status == "BILLED"

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            mocked_message_parser.assert_called_once()
