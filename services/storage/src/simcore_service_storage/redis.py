import logging
from typing import cast

from aiohttp import web
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from ._meta import APP_NAME
from .constants import APP_CONFIG_KEY
from .settings import Settings

_logger = logging.getLogger(__name__)

_APP_REDIS_KEY = "APP_REDIS_KEY"


def setup_redis(app: web.Application):
    async def _setup(app: web.Application):
        app[_APP_REDIS_KEY] = None
        settings: Settings = app[APP_CONFIG_KEY]
        assert settings.STORAGE_REDIS  # nosec
        redis_settings: RedisSettings = settings.STORAGE_REDIS
        redis_locks_dsn = redis_settings.build_redis_dsn(RedisDatabase.LOCKS)
        app[_APP_REDIS_KEY] = client = RedisClientSDK(
            redis_locks_dsn, client_name=APP_NAME
        )
        await client.setup()

        yield

        if client:
            await client.shutdown()

    app.cleanup_ctx.append(_setup)


def get_redis_client(app: web.Application) -> RedisClientSDK:
    return cast(RedisClientSDK, app[_APP_REDIS_KEY])
