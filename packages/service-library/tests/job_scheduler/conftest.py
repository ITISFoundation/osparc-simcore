from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase


@pytest.fixture
async def redis_client_sdk_job_scheduler(
    get_redis_client_sdk: Callable[
        [RedisDatabase, bool], AbstractAsyncContextManager[RedisClientSDK]
    ]
) -> AsyncIterator[RedisClientSDK]:
    async with get_redis_client_sdk(
        RedisDatabase.JOB_SCHEDULER, decode_response=False
    ) as client:
        yield client
