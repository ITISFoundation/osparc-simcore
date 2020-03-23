# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import aioredis
import pytest
import tenacity
from yarl import URL

from servicelib.redis_utils import RedisRetryPolicyUponInitialization

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def redis_config(docker_stack: Dict, devel_environ: Dict) -> Dict[str, str]:
    assert "simcore_redis" in docker_stack["services"]

    config = {
        "host": "127.0.0.1",
        "port": get_service_published_port("redis", devel_environ["REDIS_PORT"]),
    }
    return config


@pytest.fixture(scope="module")
async def redis_service(redis_config: Dict[str, str], docker_stack: Dict) -> URL:
    url = URL("redis://{host}:{port}".format(**redis_config))
    await wait_till_redis_responsive(url)
    return url


@pytest.fixture(scope="module")
async def redis_client(loop, redis_service: URL) -> aioredis.Redis:
    client = await aioredis.create_redis_pool(str(redis_service), encoding="utf-8")

    yield client

    await client.flushall()
    client.close()
    await client.wait_closed()


# HELPERS --


@tenacity.retry(**RedisRetryPolicyUponInitialization().kwargs)
async def wait_till_redis_responsive(redis_url: URL) -> None:
    client = await aioredis.create_redis_pool(str(redis_url), encoding="utf-8")
    client.close()
    await client.wait_closed()
