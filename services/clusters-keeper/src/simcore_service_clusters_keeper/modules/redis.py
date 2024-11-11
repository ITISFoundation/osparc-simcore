import logging
from typing import cast

from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME
from ..core.settings import get_application_settings

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.redis_client_sdk = None
        settings: RedisSettings = get_application_settings(app).CLUSTERS_KEEPER_REDIS
        redis_locks_dsn = settings.build_redis_dsn(RedisDatabase.LOCKS)
        app.state.redis_client_sdk = client = RedisClientSDK(
            redis_locks_dsn, client_name=APP_NAME
        )
        await client.setup()

    async def on_shutdown() -> None:
        redis_client_sdk: None | RedisClientSDK = app.state.redis_client_sdk
        if redis_client_sdk:
            await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
