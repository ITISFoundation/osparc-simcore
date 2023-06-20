# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Callable, Iterator, cast

import docker
import requests
from docker.models.containers import Container
from pydantic import HttpUrl
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from tenacity import retry, retry_if_exception_type
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
    assert await rabbit_client.ping() is True


@dataclass(frozen=True)
class PytestRabbitMessage:
    message: str
    topic: str

    def routing_key(self) -> str:
        return self.topic

    def body(self) -> bytes:
        return self.message.encode()


def _get_rabbitmq_api_params(rabbit_service: RabbitSettings) -> dict[str, str]:
    return dict(
        scheme="http",
        user=rabbit_service.RABBIT_USER,
        password=rabbit_service.RABBIT_PASSWORD.get_secret_value(),
        host=rabbit_service.RABBIT_HOST,
        port="15672",
    )


@retry(
    reraise=True,
    retry=retry_if_exception_type(AssertionError),
    wait=wait_fixed(1),
    stop=stop_after_delay(10),
)
def _assert_rabbitmq_has_connections(
    rabbit_service: RabbitSettings, num_connections: int
) -> list[str]:
    rabbit_list_connections_url = HttpUrl.build(
        **_get_rabbitmq_api_params(rabbit_service),
        path="/api/connections/",
    )
    response = requests.get(rabbit_list_connections_url, timeout=5)
    response.raise_for_status()
    list_connections = response.json()
    assert len(list_connections) == num_connections
    return [conn["name"] for conn in list_connections]


@retry(
    reraise=True,
    retry=retry_if_exception_type(AssertionError),
    wait=wait_fixed(1),
    stop=stop_after_delay(10),
)
def _assert_connection_state(
    rabbit_service: RabbitSettings, connection_name: str, *, state: str
) -> None:
    rabbit_specific_connection_url = HttpUrl.build(
        **_get_rabbitmq_api_params(rabbit_service),
        path=f"/api/connections/{connection_name}",
    )
    response = requests.get(rabbit_specific_connection_url, timeout=5)
    response.raise_for_status()
    connection = response.json()
    assert connection["state"] == state


def _close_rabbitmq_connection(
    rabbit_service: RabbitSettings, connection_name: str
) -> None:
    rabbit_specific_connection_url = HttpUrl.build(
        **_get_rabbitmq_api_params(rabbit_service),
        path=f"/api/connections/{connection_name}",
    )
    response = requests.delete(rabbit_specific_connection_url, timeout=5)
    response.raise_for_status()


@retry(
    reraise=True,
    retry=retry_if_exception_type(AssertionError),
    wait=wait_fixed(1),
    stop=stop_after_delay(20),
)
async def _assert_rabbit_client_state(
    rabbit_client: RabbitMQClient, *, healthy: bool
) -> None:
    assert rabbit_client.healthy == healthy


async def test_rabbit_server_closes_connection(
    rabbit_service: RabbitSettings,
    rabbitmq_client: Callable[[str, int], RabbitMQClient],
    docker_client: docker.client.DockerClient,
):
    _assert_rabbitmq_has_connections(rabbit_service, 0)
    rabbit_client = rabbitmq_client("tester", heartbeat=2)
    message = PytestRabbitMessage(message="blahblah", topic="topic")
    await rabbit_client.publish("test", message)
    await asyncio.sleep(5)
    connection_names = _assert_rabbitmq_has_connections(rabbit_service, 1)
    _close_rabbitmq_connection(rabbit_service, connection_names[0])
    # since the heartbeat during testing is low, the connection disappears fast
    _assert_rabbitmq_has_connections(rabbit_service, 0)

    await _assert_rabbit_client_state(rabbit_client, healthy=False)
