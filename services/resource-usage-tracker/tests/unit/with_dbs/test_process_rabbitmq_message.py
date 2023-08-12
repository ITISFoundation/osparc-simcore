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
)
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient

##################
# MATUS: probably do an integration test from this one
##################

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


@pytest.mark.testit
async def test_rabbit_client_pub_sub(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    # random_rabbit_message: Callable[..., RabbitResourceTrackingHeartbeatMessage],
    random_rabbit_message_start,
    mocked_redis_server: None,
    mocked_prometheus: mock.Mock,
    postgres_db: sa.engine.Engine,
    async_client: httpx.AsyncClient,
):
    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message_start()
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), message
    )
    # await _assert_message_received(mocked_message_parser, 1, message)
    print("yes")
