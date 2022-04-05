# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
from typing import AsyncIterator, Dict, Union

import pytest
import tenacity
from redis import asyncio as aioredis
from settings_library.redis import RedisSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

from .helpers.utils_docker import get_localhost_ip, get_service_published_port

log = logging.getLogger(__name__)


@pytest.fixture
async def redis_settings(
    docker_stack: Dict,  # stack is up
    testing_environ_vars: Dict,
) -> RedisSettings:
    """Returns the settings of a redis service that is up and responsive"""

    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_redis" in docker_stack["services"]

    port = get_service_published_port(
        "simcore_redis", testing_environ_vars["REDIS_PORT"]
    )
    # test runner is running on the host computer
    settings = RedisSettings(REDIS_HOST=get_localhost_ip(), REDIS_PORT=int(port))
    await wait_till_redis_responsive(settings.dsn)

    return settings


@pytest.fixture(scope="function")
def redis_service(
    redis_settings: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> RedisSettings:
    """Sets env vars for a redis service is up and responsive and returns its settings as well

    NOTE: Use this fixture to setup client app
    """
    monkeypatch.setenv("REDIS_HOST", redis_settings.REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", str(redis_settings.REDIS_PORT))
    return redis_settings


@pytest.fixture(scope="function")
async def redis_client(
    redis_settings: RedisSettings,
) -> AsyncIterator[aioredis.Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = aioredis.from_url(
        redis_settings.dsn, encoding="utf-8", decode_responses=True
    )

    yield client

    await client.flushall()


@pytest.fixture(scope="function")
async def redis_locks_client(
    redis_settings: RedisSettings,
) -> AsyncIterator[aioredis.Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = aioredis.from_url(
        redis_settings.dsn_locks, encoding="utf-8", decode_responses=True
    )

    yield client

    await client.flushall()


# HELPERS --


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_redis_responsive(redis_url: Union[URL, str]) -> None:
    client = aioredis.from_url(f"{redis_url}", encoding="utf-8", decode_responses=True)

    if not await client.ping():
        raise ConnectionError(f"{redis_url=} not available")
