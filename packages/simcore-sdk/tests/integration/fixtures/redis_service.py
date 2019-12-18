# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy

import aioredis
import pytest
import tenacity
from yarl import URL


@pytest.fixture(scope='module')
async def redis_service(loop, _webserver_dev_config, webserver_environ, docker_stack):
    cfg = deepcopy(_webserver_dev_config["resource_manager"]["redis"])

    host = cfg["host"]
    port = cfg["port"]
    url = URL(f"redis://{host}:{port}")

    assert await wait_till_redis_responsive(url)

    yield url


@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(60))
async def wait_till_redis_responsive(redis_url: URL) -> bool:
    client = await aioredis.create_redis_pool(str(redis_url), encoding="utf-8")
    client.close()
    await client.wait_closed()
    return True

@pytest.fixture(scope='module')
async def redis_client(loop, redis_service):
    client = await aioredis.create_redis_pool(str(redis_service), encoding="utf-8")
    yield client

    await client.flushall()
    client.close()
    await client.wait_closed()
