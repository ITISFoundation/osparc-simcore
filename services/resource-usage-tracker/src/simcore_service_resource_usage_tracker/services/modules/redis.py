import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI, Request
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from ..._meta import APP_NAME

_logger = logging.getLogger(__name__)


def configure_redis(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _redis_lifespan(app: FastAPI) -> AsyncIterator[State]:
        app.state.redis_client_sdk = None
        try:
            with log_context(_logger, logging.INFO, msg="RUT startup Redis"):
                settings: RedisSettings = app.state.settings.RESOURCE_USAGE_TRACKER_REDIS
                redis_locks_dsn = settings.build_redis_dsn(RedisDatabase.LOCKS)
                app.state.redis_client_sdk = RedisClientSDK(redis_locks_dsn, client_name=APP_NAME)
                await app.state.redis_client_sdk.setup()
            yield {}
        finally:
            redis_client_sdk: None | RedisClientSDK = app.state.redis_client_sdk
            if redis_client_sdk:
                with log_context(_logger, logging.INFO, msg="RUT shutdown Redis"):
                    await redis_client_sdk.shutdown()

    app_lifespan.add(_redis_lifespan)


def get_redis_lock_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)


def get_redis_lock_client_from_request(request: Request) -> RedisClientSDK:
    return get_redis_lock_client(request.app)
