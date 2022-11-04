# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio

import pytest
from faker import Faker
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


async def test_rabbit_client_pub_sub(
    rabbit_client_name: str, rabbit_service: RabbitSettings, faker: Faker
):
    publisher = RabbitMQClient(f"{rabbit_client_name}_publisher", rabbit_service)
    assert publisher
    consumer = RabbitMQClient(f"{rabbit_client_name}_consumer", rabbit_service)
    assert consumer

    queue_name = faker.pystr()
    await publisher.publish(queue_name)

    received_messages = []

    async def _message_parser(message) -> bool:
        print(f"<-- received message {message}")
        received_messages.append(message)
        return True

    await consumer.consume(queue_name, _message_parser)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert len(received_messages) == 1, "no message received!"

    await asyncio.gather(*(client.close() for client in (publisher, consumer)))
    for client in (publisher, consumer):
        assert client._channel_pool
        assert client._channel_pool.is_closed
        assert publisher._connection_pool
        assert publisher._connection_pool.is_closed
