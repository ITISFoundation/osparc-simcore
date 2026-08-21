from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import configure_redis_client_sdk
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase

from ..._meta import APP_NAME


def configure_redis(app: FastAPI, app_lifespan: LifespanManager[FastAPI]) -> None:
    configure_redis_client_sdk(
        app_lifespan,
        settings=app.state.settings.EFS_GUARDIAN_REDIS,
        database=RedisDatabase.LOCKS,
        client_name=APP_NAME,
        app_state_attr="redis_lock_client_sdk",
    )


def get_redis_lock_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_lock_client_sdk)
