import logging
from typing import cast

from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase

from .._meta import APP_NAME
from ..core.settings import get_application_settings

_logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.redis_client_sdk = None
        redis_settings = get_application_settings(app).STORAGE_REDIS
        redis_locks_dsn = redis_settings.build_redis_dsn(RedisDatabase.LOCKS)
        app.state.redis_client_sdk = RedisClientSDK(
            redis_locks_dsn, client_name=APP_NAME
        )
        await app.state.redis_client_sdk.setup()

    async def on_shutdown() -> None:
        redis_client_sdk = app.state.redis_client_sdk
        if redis_client_sdk:
            await cast(RedisClientSDK, app.state.redis_client_sdk).shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
