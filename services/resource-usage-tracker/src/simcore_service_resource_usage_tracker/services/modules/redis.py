from typing import cast

from fastapi import FastAPI, Request
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import configure_redis_client_sdk
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from ..._meta import APP_NAME


def configure_redis(
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


def get_redis_lock_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)


def get_redis_lock_client_from_request(request: Request) -> RedisClientSDK:
    return get_redis_lock_client(request.app)
