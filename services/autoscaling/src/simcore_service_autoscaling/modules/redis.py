import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME

logger = logging.getLogger(__name__)


async def redis_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.redis_client_sdk = None
    settings: RedisSettings = app.state.settings.AUTOSCALING_REDIS
    redis_locks_dsn = settings.build_redis_dsn(RedisDatabase.LOCKS)
    app.state.redis_client_sdk = RedisClientSDK(redis_locks_dsn, client_name=APP_NAME)
    await app.state.redis_client_sdk.setup()
    try:
        yield {}
    finally:
        redis_client_sdk: None | RedisClientSDK = app.state.redis_client_sdk
        if redis_client_sdk:
            await redis_client_sdk.shutdown()


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
