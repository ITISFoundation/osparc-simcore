# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import pytest
from faker import Faker
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings

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
    assert client._channel_pool
    assert client.client_name == rabbit_client_name
    assert client.settings == rabbit_service


async def test_rabbit_client_pub_sub(
    rabbit_client_name: str, rabbit_service: RabbitSettings, faker: Faker
):
    publisher = RabbitMQClient(f"{rabbit_client_name}_publisher", rabbit_service)
    assert publisher
    consumer = RabbitMQClient(f"{rabbit_client_name}_consumer", rabbit_service)
    assert consumer

    queue_name = faker.pystr()
    await publisher.publish(queue_name)
    await consumer.consume(queue_name)
