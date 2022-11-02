# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def test_rabbit_client(rabbit_service: RabbitSettings):
    client = RabbitMQClient(rabbit_service)
    # check it is correctly initialized
    assert client._connection_pool
    assert client._channel_pool
