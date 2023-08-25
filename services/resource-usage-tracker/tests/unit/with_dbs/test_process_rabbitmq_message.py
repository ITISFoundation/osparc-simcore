import asyncio
from datetime import datetime, timezone
from typing import Any, Callable
from unittest import mock

import faker
import httpx
import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingBaseMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
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

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def rabbit_client_name(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock(return_value=True)


@pytest.fixture
def random_rabbit_message_heartbeat(
    faker: Faker,
) -> Callable[..., RabbitResourceTrackingHeartbeatMessage]:
    def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingHeartbeatMessage:
        msg_config = {"service_run_id": faker.uuid4(), **kwargs}

        return RabbitResourceTrackingHeartbeatMessage(**msg_config)

    return _creator


@pytest.fixture
def random_rabbit_message_start(
    faker: Faker,
) -> Callable[..., RabbitResourceTrackingStartedMessage]:
    def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingStartedMessage:
        msg_config = {
            "channel_name": "io.simcore.service.tracking",
            "service_run_id": faker.uuid4(),
            "created_at": datetime.now(timezone.utc),
            "wallet_id": faker.pyint(),
            "wallet_name": faker.pystr(),
            "product_name": "osparc",
            "simcore_user_agent": faker.pystr(),
            "user_id": faker.pyint(),
            "user_email": faker.email(),
            "project_id": faker.uuid4(),
            "project_name": faker.pystr(),
            "node_id": faker.uuid4(),
            "node_name": faker.pystr(),
            "service_key": "simcore/services/comp/itis/sleeper",
            "service_version": "2.1.6",
            "service_type": "computational",
            "service_resources": {
                "container": {
                    "image": "simcore/services/comp/itis/sleeper:2.1.6",
                    "resources": {
                        "CPU": {"limit": 0.1, "reservation": 0.1},
                        "RAM": {"limit": 134217728, "reservation": 134217728},
                    },
                    "boot_modes": ["CPU"],
                }
            },
            "service_additional_metadata": {},
            **kwargs,
        }

        return RabbitResourceTrackingStartedMessage(**msg_config)

    return _creator


@pytest.fixture()
def resource_tracker_service_run_db(postgres_db: sa.engine.Engine):
    with postgres_db.connect() as con:
        # removes all service runs before continuing
        con.execute(resource_tracker_service_runs.delete())
        yield
        con.execute(resource_tracker_service_runs.delete())


async def test_process_event_functions(
    mocked_setup_rabbitmq,
    random_rabbit_message_start,
    mocked_redis_server: None,
    mocked_prometheus: mock.Mock,
    postgres_db: sa.engine.Engine,
    # async_client: httpx.AsyncClient,
    resource_tracker_service_run_db,
    initialized_app,
):
    engine = initialized_app.state.engine

    msg = random_rabbit_message_start()
    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )
    await _process_start_event(resource_tacker_repo, msg)

    await asyncio.sleep(2.5)
    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await _process_heartbeat_event(resource_tacker_repo, heartbeat_msg)

    await asyncio.sleep(2.5)
    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await _process_stop_event(resource_tacker_repo, stopped_msg)


async def _assert_db_row(
    postgres_db, service_run_id: str, expected_status: str
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.2),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            with postgres_db.connect() as con:
                # removes all projects before continuing
                con.execute(resource_tracker_service_runs.select())
                result = con.execute(
                    sa.select(resource_tracker_service_runs).where(
                        resource_tracker_service_runs.c.service_run_id == service_run_id
                    )
                )
                row = result.first()
                assert row
                assert row[1] == service_run_id
                assert row[20] == expected_status


@pytest.mark.testit
async def test_process_events_via_rabbit(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_rabbit_message_start,
    mocked_redis_server: None,
    mocked_prometheus: mock.Mock,
    postgres_db: sa.engine.Engine,
    async_client: httpx.AsyncClient,
    resource_tracker_service_run_db,
):
    publisher = rabbitmq_client("publisher")
    msg = random_rabbit_message_start()
    await publisher.publish(RabbitResourceTrackingBaseMessage.get_channel_name(), msg)
    await _assert_db_row(postgres_db, msg.service_run_id, "RUNNING")

    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), heartbeat_msg
    )
    await _assert_db_row(postgres_db, msg.service_run_id, "RUNNING")

    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), stopped_msg
    )
    await _assert_db_row(postgres_db, msg.service_run_id, "SUCCESS")
