from collections.abc import Callable
from datetime import datetime, timezone

# NOTE: This test fails when running locally and you are connected through VPN: Temporary failure in name resolution [Errno -3]
import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingBaseMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from servicelib.rabbitmq import RabbitMQClient

from .conftest import assert_service_runs_db_row

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_process_events_via_rabbit(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    initialized_app,
    resource_tracker_service_run_db,
):
    publisher = rabbitmq_client("publisher")
    msg = random_rabbit_message_start(
        wallet_id=None, wallet_name=None, pricing_plan_id=None, pricing_detail_id=None
    )
    await publisher.publish(RabbitResourceTrackingBaseMessage.get_channel_name(), msg)
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
