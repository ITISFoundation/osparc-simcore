import logging
from typing import cast

from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME
from ..constants import APP_CONFIG_KEY
from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_APP_REDIS_KEY = "APP_REDIS_KEY"


def setup_redis(app: FastAPI):
    async def _setup(app: FastAPI):
        app[_APP_REDIS_KEY] = None
        settings: ApplicationSettings = app[APP_CONFIG_KEY]
        assert settings.STORAGE_REDIS  # nosec
        redis_settings: RedisSettings = settings.STORAGE_REDIS
        redis_locks_dsn = redis_settings.build_redis_dsn(RedisDatabase.LOCKS)
        app[_APP_REDIS_KEY] = client = RedisClientSDK(
            redis_locks_dsn, client_name=APP_NAME
        )

        yield

        if client:
            await client.shutdown()

    app.cleanup_ctx.append(_setup)


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app[_APP_REDIS_KEY])
