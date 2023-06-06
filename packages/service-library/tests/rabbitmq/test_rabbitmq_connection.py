# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import contextlib
from typing import Callable, Iterator, cast

import docker
from docker.models.containers import Container
from servicelib.rabbitmq import RabbitMQClient
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@contextlib.contextmanager
def paused_container(
    docker_client: docker.client.DockerClient, container_name: str
) -> Iterator[None]:
    paused_containers = []
    containers = docker_client.containers.list(filters={"name": container_name})
    for container in containers:
        container = cast(Container, container)
        container.pause()
        container.reload()
        assert container.status == "paused"
        paused_containers.append(container)

    yield

    for container in paused_containers:
        container = cast(Container, container)
        container.unpause()
        container.reload()
        assert container.status == "running"


async def test_rabbit_client_lose_connection(
    cleanup_check_rabbitmq_server_has_no_errors: None,
    rabbitmq_client: Callable[[str], RabbitMQClient],
    docker_client: docker.client.DockerClient,
):
    rabbit_client = rabbitmq_client("pinger")
    assert await rabbit_client.ping() is True
    with paused_container(docker_client, "rabbit"):
        # check that connection was lost
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(15), wait=wait_fixed(0.5), reraise=True
        ):
            with attempt:
                assert await rabbit_client.ping() is False
    # now the connection is back
    # assert await rabbit_client.ping() is True
