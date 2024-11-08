from collections.abc import Callable
from datetime import datetime, timezone

import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_resource_usage_tracker.services.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)
from simcore_service_resource_usage_tracker.services.process_message_running_service import (
    _process_heartbeat_event,
    _process_start_event,
    _process_stop_event,
)

from .conftest import assert_service_runs_db_row

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_process_event_functions(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db,
    initialized_app,
):
    engine = initialized_app.state.engine
    publisher = create_rabbitmq_client("publisher")

    msg = random_rabbit_message_start(
        wallet_id=None,
        wallet_name=None,
        pricing_plan_id=None,
        pricing_unit_id=None,
        pricing_unit_cost_id=None,
    )
    resource_tracker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )
    await _process_start_event(resource_tracker_repo, msg, publisher)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output.stopped_at is None
    assert output.service_run_status == "RUNNING"
    first_occurence_of_last_heartbeat_at = output.last_heartbeat_at

    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await _process_heartbeat_event(resource_tracker_repo, heartbeat_msg, publisher)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output.stopped_at is None
    assert output.service_run_status == "RUNNING"
    assert first_occurence_of_last_heartbeat_at < output.last_heartbeat_at

    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await _process_stop_event(resource_tracker_repo, stopped_msg, publisher)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output.stopped_at is not None
    assert output.service_run_status == "SUCCESS"
