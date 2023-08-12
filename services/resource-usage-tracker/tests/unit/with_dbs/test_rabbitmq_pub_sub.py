from typing import Any, Callable
from unittest import mock

import faker
import pytest
from faker import Faker
from models_library.rabbitmq_messages import RabbitResourceTrackingHeartbeatMessage
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def rabbit_client_name(faker: Faker) -> str:
    return faker.pystr()


# async def test_rabbit_client(
#     rabbit_client_name: str,
#     rabbit_service: RabbitSettings,
# ):
#     client = RabbitMQClient(rabbit_client_name, rabbit_service)
#     assert client
#     # check it is correctly initialized
#     assert client._connection_pool  # noqa: SLF001
#     assert not client._connection_pool.is_closed  # noqa: SLF001
#     assert client._channel_pool  # noqa: SLF001
#     assert not client._channel_pool.is_closed  # noqa: SLF001
#     assert client.client_name == rabbit_client_name
#     assert client.settings == rabbit_service
#     await client.close()
#     assert client._connection_pool  # noqa: SLF001
#     assert client._connection_pool.is_closed  # noqa: SLF001


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
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = "matus-exchange"
    await consumer.subscribe(
        exchange_name, mocked_message_parser, exclusive_queue=False
    )
    await publisher.publish(exchange_name, message)
    # await _assert_message_received(mocked_message_parser, 1, message)
    print("yes")
