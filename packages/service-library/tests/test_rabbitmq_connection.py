# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Callable

import docker
from servicelib.rabbitmq import RabbitMQClient
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


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
