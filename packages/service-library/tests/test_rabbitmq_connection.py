# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import asyncio
from typing import AsyncIterator, Callable

import docker
import pytest
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


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


async def test_rabbit_client_lose_connection(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    docker_client: docker.client.DockerClient,
):
    rabbit_client = rabbitmq_client("pinger")
    assert await rabbit_client.ping() is True
    # now let's put down the rabbit service
    for rabbit_docker_service in (
        docker_service
        for docker_service in docker_client.services.list()
        if "rabbit" in docker_service.name  # type: ignore
    ):
        rabbit_docker_service.remove()  # type: ignore
    # check that connection was lost
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(60), wait=wait_fixed(0.5), reraise=True
    ):
        with attempt:
            assert await rabbit_client.ping() is False
