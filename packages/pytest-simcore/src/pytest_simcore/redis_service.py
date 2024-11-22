# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import tenacity
from pytest_mock import MockerFixture
from redis.asyncio import Redis, from_url
from settings_library.basic_types import PortInt
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.typing_env import EnvVarsDict

log = logging.getLogger(__name__)


@pytest.fixture
async def redis_settings(
    docker_stack: dict,  # stack is up
    env_vars_for_docker_compose: EnvVarsDict,
) -> RedisSettings:
    """Returns the settings of a redis service that is up and responsive"""

    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_redis" in docker_stack["services"]

    port = get_service_published_port(
        "simcore_redis", int(env_vars_for_docker_compose["REDIS_PORT"])
    )
    # test runner is running on the host computer
    settings = RedisSettings(
        REDIS_HOST=get_localhost_ip(),
        REDIS_PORT=PortInt(port),
        REDIS_PASSWORD=env_vars_for_docker_compose["REDIS_PASSWORD"],
    )
    await wait_till_redis_responsive(settings.build_redis_dsn(RedisDatabase.RESOURCES))

    return settings


@pytest.fixture()
def redis_service(
    redis_settings: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> RedisSettings:
    """Sets env vars for a redis service is up and responsive and returns its settings as well

    NOTE: Use this fixture to setup client app
    """
    monkeypatch.setenv("REDIS_HOST", redis_settings.REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", str(redis_settings.REDIS_PORT))
    monkeypatch.setenv(
        "REDIS_PASSWORD", redis_settings.REDIS_PASSWORD.get_secret_value()
    )
    return redis_settings


@pytest.fixture()
async def redis_client(
    redis_settings: RedisSettings,
) -> AsyncIterator[Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = from_url(
        redis_settings.build_redis_dsn(RedisDatabase.RESOURCES),
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    await client.flushall()
    await client.aclose(close_connection_pool=True)


@pytest.fixture()
async def redis_locks_client(
    redis_settings: RedisSettings,
) -> AsyncIterator[Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = from_url(
        redis_settings.build_redis_dsn(RedisDatabase.LOCKS),
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    await client.flushall()
    await client.aclose(close_connection_pool=True)


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_redis_responsive(redis_url: URL | str) -> None:
    client = from_url(f"{redis_url}", encoding="utf-8", decode_responses=True)
    try:
        if not await client.ping():
            msg = f"{redis_url=} not available"
            raise ConnectionError(msg)
    finally:
        await client.aclose(close_connection_pool=True)


@pytest.fixture
def mock_redis_socket_timeout(mocker: MockerFixture) -> None:
    # lowered to allow CI to properly shutdown RedisClientSDK instances
    from servicelib import redis

    mocker.patch.object(redis, "_DEFAULT_SOCKET_TIMEOUT", timedelta(seconds=1))
