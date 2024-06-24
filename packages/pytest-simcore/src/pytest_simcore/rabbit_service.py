# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

import aio_pika
import pytest
import tenacity
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.typing_env import EnvVarsDict

_logger = logging.getLogger(__name__)


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
def rabbit_env_vars_dict(
    docker_stack: dict,
    testing_environ_vars: dict,
) -> EnvVarsDict:
    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]

    port = get_service_published_port("rabbit", testing_environ_vars["RABBIT_PORT"])

    return {
        "RABBIT_USER": testing_environ_vars["RABBIT_USER"],
        "RABBIT_PASSWORD": testing_environ_vars["RABBIT_PASSWORD"],
        "RABBIT_HOST": get_localhost_ip(),
        "RABBIT_PORT": f"{port}",
        "RABBIT_SECURE": testing_environ_vars["RABBIT_SECURE"],
    }


@pytest.fixture
async def rabbit_settings(rabbit_env_vars_dict: EnvVarsDict) -> RabbitSettings:
    """Returns the settings of a rabbit service that is up and responsive"""

    settings = RabbitSettings.parse_obj(rabbit_env_vars_dict)
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
    monkeypatch.setenv("RABBIT_PORT", f"{rabbit_settings.RABBIT_PORT}")
    monkeypatch.setenv("RABBIT_USER", rabbit_settings.RABBIT_USER)
    monkeypatch.setenv("RABBIT_SECURE", f"{rabbit_settings.RABBIT_SECURE}")
    monkeypatch.setenv(
        "RABBIT_PASSWORD", rabbit_settings.RABBIT_PASSWORD.get_secret_value()
    )

    return rabbit_settings


@pytest.fixture
async def create_rabbitmq_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], RabbitMQClient]]:
    created_clients: list[RabbitMQClient] = []

    def _creator(client_name: str, *, heartbeat: int = 60) -> RabbitMQClient:
        # pylint: disable=protected-access
        client = RabbitMQClient(
            f"pytest_{client_name}", rabbit_service, heartbeat=heartbeat
        )
        assert client
        assert client._connection_pool  # noqa: SLF001
        assert not client._connection_pool.is_closed  # noqa: SLF001
        assert client._channel_pool  # noqa: SLF001
        assert not client._channel_pool.is_closed  # noqa: SLF001
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator

    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))


@pytest.fixture
async def rabbitmq_rpc_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], Awaitable[RabbitMQRPCClient]]]:
    created_clients = []

    async def _creator(client_name: str, *, heartbeat: int = 60) -> RabbitMQRPCClient:
        client = await RabbitMQRPCClient.create(
            client_name=f"pytest_{client_name}",
            settings=rabbit_service,
            heartbeat=heartbeat,
        )
        assert client
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator
    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))


async def rabbitmq_client(create_rabbitmq_client):
    # NOTE: Legacy fixture
    # Use create_rabbitmq_client instead of rabbitmq_client
    # SEE docs/coding-conventions.md::CC4
    return create_rabbitmq_client
