from collections.abc import AsyncIterator

import pytest
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings


async def _cleanup_redis_data(client: RedisClientSDK) -> None:
    await client.redis.flushall()


@pytest.fixture
async def redis_client_sdk_deferred_tasks(
    redis_service: RedisSettings,
) -> AsyncIterator[RedisClientSDK]:

    client = RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.DEFERRED_TASKS),
        decode_responses=False,
        client_name="pytest-deferred_tasks",
    )
    await client.setup()

    await _cleanup_redis_data(client)

    yield client

    await _cleanup_redis_data(client)
    await client.shutdown()
