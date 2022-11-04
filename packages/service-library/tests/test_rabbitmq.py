# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
from typing import AsyncIterator, Callable

import pytest
from faker import Faker
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def rabbit_client_name(faker: Faker) -> str:
    return faker.pystr()


async def test_rabbit_client(rabbit_client_name: str, rabbit_service: RabbitSettings):
    client = RabbitMQClient(rabbit_client_name, rabbit_service)
    assert client
    # check it is correctly initialized
    assert client._connection_pool
    assert not client._connection_pool.is_closed
    assert client._channel_pool
    assert not client._channel_pool.is_closed
    assert client.client_name == rabbit_client_name
    assert client.settings == rabbit_service
    await client.close()
    assert client._connection_pool
    assert client._connection_pool.is_closed
    assert client._channel_pool
    assert client._channel_pool.is_closed


@pytest.fixture
async def rabbitmq_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], RabbitMQClient]]:
    created_clients = []

    def _creator(client_name: str) -> RabbitMQClient:
        client = RabbitMQClient(f"pytest_{client_name}", rabbit_service)
        assert client
        assert client._connection_pool
        assert not client._connection_pool.is_closed
        assert client._channel_pool
        assert not client._channel_pool.is_closed
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator
    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))
    for client in created_clients:
        assert client._channel_pool
        assert client._channel_pool.is_closed


@pytest.fixture
def random_queue_name(faker: Faker) -> str:
    return faker.pystr()


async def test_rabbit_client_pub_sub(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_queue_name: str,
    faker: Faker,
    mocker: MockerFixture,
):
    publisher = rabbitmq_client("publisher")
    consumer = rabbitmq_client("consumer")

    await publisher.publish(random_queue_name)

    mocked_message_parser = mocker.MagicMock(return_value=True)
    await consumer.consume(random_queue_name, mocked_message_parser)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            mocked_message_parser.assert_called_once()
