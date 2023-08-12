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
)
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient

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
def random_rabbit_message(
    faker: Faker,
) -> Callable[..., RabbitResourceTrackingHeartbeatMessage]:
    def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingHeartbeatMessage:
        msg_config = {"service_run_id": faker.text(), **kwargs}

        return RabbitResourceTrackingHeartbeatMessage(**msg_config)

    return _creator


@pytest.mark.testit
async def test_rabbit_client_pub_sub(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., RabbitResourceTrackingHeartbeatMessage],
    mocked_redis_server: None,
    mocked_prometheus: mock.Mock,
    postgres_db: sa.engine.Engine,
    async_client: httpx.AsyncClient,
):

    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()
    await publisher.publish(
        RabbitResourceTrackingBaseMessage.get_channel_name(), message
    )
    # await _assert_message_received(mocked_message_parser, 1, message)
    print("yes")
