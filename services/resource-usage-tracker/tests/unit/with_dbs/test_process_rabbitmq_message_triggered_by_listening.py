from datetime import datetime, timezone
from typing import Callable

import pytest
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


@pytest.mark.skip(
    reason="Failes when connected through VPN: Temporary failure in name resolution [Errno -3]"
)
async def test_process_events_via_rabbit(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    initialized_app,
    resource_tracker_service_run_db,
):
    publisher = rabbitmq_client("publisher")
    msg = random_rabbit_message_start()
    await publisher.publish(RabbitResourceTrackingBaseMessage.get_channel_name(), msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[20] == "RUNNING"  # status

    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), heartbeat_msg
    )
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[20] == "RUNNING"  # status

    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), stopped_msg
    )
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[20] == "SUCCESS"  # status
