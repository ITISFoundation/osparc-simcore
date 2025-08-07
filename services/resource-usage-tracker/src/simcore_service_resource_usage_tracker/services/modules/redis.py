import logging
from typing import cast

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from ..._meta import APP_NAME

_logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="RUT startup Redis",
        ):
            app.state.redis_client_sdk = None
            settings: RedisSettings = app.state.settings.RESOURCE_USAGE_TRACKER_REDIS
            redis_locks_dsn = settings.build_redis_dsn(RedisDatabase.LOCKS)
            app.state.redis_client_sdk = RedisClientSDK(
                redis_locks_dsn, client_name=APP_NAME
            )
            await app.state.redis_client_sdk.setup()

    async def on_shutdown() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="RUT shutdown Redis",
        ):
            redis_client_sdk: None | RedisClientSDK = app.state.redis_client_sdk
            if redis_client_sdk:
                await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_lock_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
