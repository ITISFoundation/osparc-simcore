from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import configure_redis_client_sdk
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME


def configure_redis_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings,
) -> None:
    configure_redis_client_sdk(
        app_lifespan,
        settings=settings,
        database=RedisDatabase.LOCKS,
        client_name=APP_NAME,
    )


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
