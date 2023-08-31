from datetime import datetime, timezone

import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from simcore_service_resource_usage_tracker.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)
from simcore_service_resource_usage_tracker.resource_tracker_process_messages import (
    _process_heartbeat_event,
    _process_start_event,
    _process_stop_event,
)

from .conftest import assert_service_runs_db_row

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_process_event_functions(
    mocked_setup_rabbitmq,
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db,
    initialized_app,
):
    engine = initialized_app.state.engine

    msg = random_rabbit_message_start(
        wallet_id=None, wallet_name=None, pricing_plan_id=None, pricing_detail_id=None
    )
    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )
    await _process_start_event(resource_tacker_repo, msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[20] is None  # stopped_at
    assert output[21] == "RUNNING"  # status
    first_occurence_of_last_heartbeat_at = output[23]  # last_heartbeat_at

    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await _process_heartbeat_event(resource_tacker_repo, heartbeat_msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[20] is None  # stopped_at
    assert output[21] == "RUNNING"  # status
    first_occurence_of_last_heartbeat_at < output[23]  # last_heartbeat_at

    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await _process_stop_event(resource_tacker_repo, stopped_msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[20] is not None  # stopped_at
    assert output[21] == "SUCCESS"  # status
