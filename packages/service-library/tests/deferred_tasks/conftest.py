from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase


@pytest.fixture
async def redis_client_sdk_deferred_tasks(
    get_in_process_redis_client_sdk: Callable[
        [RedisDatabase, bool], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterator[RedisClientSDK]:
    async with get_in_process_redis_client_sdk(
        RedisDatabase.DEFERRED_TASKS, decode_response=False
    ) as client:
        yield client
