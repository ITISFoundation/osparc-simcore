# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Callable, Iterator, cast

import docker
import pytest
from docker.models.containers import Container
from servicelib.rabbitmq import RabbitMQClient
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def paused_container(
    docker_client: docker.client.DockerClient,
) -> Iterator[Callable[[str], None]]:
    paused_containers = []

    def _pauser(container_name: str) -> None:
        containers = docker_client.containers.list(filters={"name": container_name})
        for container in containers:
            container = cast(Container, container)
            container.pause()
            paused_containers.append(container)

    yield _pauser
    for container in paused_containers:
        container = cast(Container, container)
        container.unpause()


async def test_rabbit_client_lose_connection(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    docker_client: docker.client.DockerClient,
    paused_container: Callable[[str], None],
):
    rabbit_client = rabbitmq_client("pinger")
    assert await rabbit_client.ping() is True
    paused_container("rabbit")
    # check that connection was lost
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(15), wait=wait_fixed(0.5), reraise=True
    ):
        with attempt:
            assert await rabbit_client.ping() is False
