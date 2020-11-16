import asyncio
import logging

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from typing import Dict

import aioredis
import pytest
import tenacity
from models_library.settings.redis import RedisConfig
from yarl import URL

from .helpers.utils_docker import get_service_published_port

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def loop(request) -> asyncio.AbstractEventLoop:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def redis_config(loop, docker_stack: Dict, devel_environ: Dict) -> RedisConfig:
    assert "simcore_redis" in docker_stack["services"]

    # test runner is running on the host computer
    config = RedisConfig(
        host="127.0.0.1",
        port=get_service_published_port("simcore_redis", devel_environ["REDIS_PORT"]),
    )
    await wait_till_redis_responsive(config.dsn)
    return config


@pytest.fixture(scope="function")
async def redis_service(redis_config: RedisConfig, monkeypatch) -> RedisConfig:
    monkeypatch.setenv("REDIS_HOST", redis_config.host)
    monkeypatch.setenv("REDIS_PORT", str(redis_config.port))
    return redis_config


@pytest.fixture(scope="module")
async def redis_client(loop, redis_config: RedisConfig) -> aioredis.Redis:
    client = await aioredis.create_redis_pool(redis_config.dsn, encoding="utf-8")

    yield client

    await client.flushall()
    client.close()
    await client.wait_closed()


# HELPERS --
@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_attempt(60),
    before_sleep=tenacity.before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_redis_responsive(redis_url: URL) -> None:
    client = await aioredis.create_redis_pool(str(redis_url), encoding="utf-8")
    client.close()
    await client.wait_closed()
