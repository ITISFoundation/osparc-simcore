from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase


@pytest.fixture
async def redis_client_sdk_deferred_tasks(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ]
) -> AsyncIterator[RedisClientSDK]:
    async with get_redis_client_sdk(RedisDatabase.DEFERRED_TASKS) as client:
        yield client
