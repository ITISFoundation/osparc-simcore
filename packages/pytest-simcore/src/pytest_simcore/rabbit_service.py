# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
from typing import AsyncIterator, Callable, Iterator, cast

import aio_pika
import docker
import pytest
import tenacity
from docker.models.containers import Container as DockerContainer
from servicelib.rabbitmq import RabbitMQClient
from settings_library.basic_types import PortInt
from settings_library.rabbit import RabbitSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_localhost_ip, get_service_published_port

_logger = logging.getLogger(__name__)


@pytest.fixture
def assert_rabbitmq_has_no_errors(
    docker_client: docker.client.DockerClient,
) -> Iterator[None]:
    yield
    print("--> checking for errors/warnings in rabbitmq logs...")
    containers = docker_client.containers.list(filters={"name": "rabbit"})
    assert len(containers) == 1, "missing rabbit container!"
    rabbit_container: DockerContainer = cast(DockerContainer, containers[0])
    rabbit_logs: bytes = rabbit_container.logs()
    converted_logs = rabbit_logs.decode().splitlines()
    warning_logs = [log for log in converted_logs if "warning" in log]
    error_logs = [log for log in converted_logs if "error" in log]
    RABBIT_SKIPPED_WARNINGS = [
        "rebuilding indices from scratch",
    ]
    filtered_warning_logs = [
        log
        for log in warning_logs
        if all(w not in log for w in RABBIT_SKIPPED_WARNINGS)
    ]
    assert not filtered_warning_logs
    assert not error_logs
    print("<-- no error founds in rabbitmq server logs, that's great. good job!")


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
async def wait_till_rabbit_responsive(url: str) -> None:
    async with await aio_pika.connect(url):
        ...


@pytest.fixture
async def rabbit_settings(
    docker_stack: dict,
    testing_environ_vars: dict,
) -> RabbitSettings:
    """Returns the settings of a rabbit service that is up and responsive"""

    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]

    port = get_service_published_port("rabbit", testing_environ_vars["RABBIT_PORT"])

    settings = RabbitSettings(
        RABBIT_USER=testing_environ_vars["RABBIT_USER"],
        RABBIT_PASSWORD=testing_environ_vars["RABBIT_PASSWORD"],
        RABBIT_HOST=get_localhost_ip(),
        RABBIT_PORT=PortInt(port),
    )

    await wait_till_rabbit_responsive(settings.dsn)

    return settings


@pytest.fixture
async def rabbit_service(
    rabbit_settings: RabbitSettings, monkeypatch: pytest.MonkeyPatch
) -> RabbitSettings:
    """Sets env vars for a rabbit service is up and responsive and returns its settings as well

    NOTE: Use this fixture to setup client app
    """
    monkeypatch.setenv("RABBIT_HOST", rabbit_settings.RABBIT_HOST)
    monkeypatch.setenv("RABBIT_PORT", str(rabbit_settings.RABBIT_PORT))
    monkeypatch.setenv("RABBIT_USER", rabbit_settings.RABBIT_USER)
    monkeypatch.setenv(
        "RABBIT_PASSWORD", rabbit_settings.RABBIT_PASSWORD.get_secret_value()
    )

    return rabbit_settings


@pytest.fixture
async def rabbitmq_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], RabbitMQClient]]:
    created_clients = []

    def _creator(client_name: str) -> RabbitMQClient:
        client = RabbitMQClient(f"pytest_{client_name}", rabbit_service)
        assert client
        assert client._connection_pool  # pylint: disable=protected-access
        assert not client._connection_pool.is_closed  # pylint: disable=protected-access
        assert client._channel_pool  # pylint: disable=protected-access
        assert not client._channel_pool.is_closed  # pylint: disable=protected-access
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator
    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))
