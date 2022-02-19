# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import warnings
from typing import AsyncIterator, Dict, Union

import aioredis
import pytest
import tenacity
from models_library.settings.redis import RedisConfig
from settings_library.redis import RedisSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

from .helpers.utils_docker import get_service_published_port

log = logging.getLogger(__name__)


@pytest.fixture
async def redis_service_up_settings(
    docker_stack: Dict,  # stack is up
    testing_environ_vars: Dict,
    monkeypatch: pytest.MonkeyPatch,
) -> RedisSettings:
    """Settings of a redis service that is responsive"""

    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_redis" in docker_stack["services"]

    port = get_service_published_port(
        "simcore_redis", testing_environ_vars["REDIS_PORT"]
    )
    # test runner is running on the host computer
    settings = RedisSettings(REDIS_HOST="127.0.0.1", REDIS_PORT=int(port))

    await wait_till_redis_responsive(settings.dsn)
    return settings


@pytest.fixture(scope="function")
async def redis_config(docker_stack: Dict, testing_environ_vars: Dict) -> RedisConfig:
    warnings.warn(
        "This fixture uses deprecated RedisConfig and will be replaced by redis_service.redis_service_up_settings",
        DeprecationWarning,
    )

    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_redis" in docker_stack["services"]

    # test runner is running on the host computer
    config = RedisConfig(
        host="127.0.0.1",
        port=get_service_published_port(
            "simcore_redis", testing_environ_vars["REDIS_PORT"]
        ),
    )
    await wait_till_redis_responsive(str(config.dsn))
    return config


@pytest.fixture(scope="function")
def redis_service(redis_config: RedisConfig, monkeypatch) -> RedisConfig:
    warnings.warn(
        "This fixture uses deprecated RedisConfig and will be replaced by redis_service.redis_service_up_settings",
        DeprecationWarning,
    )
    # WARNING: be careful with envs since now they affect directly app settings!
    monkeypatch.setenv("REDIS_HOST", redis_config.host)
    monkeypatch.setenv("REDIS_PORT", str(redis_config.port))
    return redis_config


@pytest.fixture(scope="function")
async def redis_client(
    redis_service_up_settings: RedisSettings,
) -> AsyncIterator[aioredis.Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = await aioredis.create_redis_pool(
        redis_service_up_settings.dsn, encoding="utf-8"
    )

    yield client

    await client.flushall()
    client.close()
    await client.wait_closed()


# HELPERS --


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_redis_responsive(redis_url: Union[URL, str]) -> None:
    client = await aioredis.create_redis_pool(str(redis_url), encoding="utf-8")
    client.close()
    await client.wait_closed()
