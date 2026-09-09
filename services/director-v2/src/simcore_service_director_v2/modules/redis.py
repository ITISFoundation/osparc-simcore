from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import configure_redis_clients_manager as _configure_redis_clients_manager
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME


def configure_redis(app_lifespan: LifespanManager, *, settings: RedisSettings) -> None:
    _configure_redis_clients_manager(
        app_lifespan,
        settings=settings,
        databases_configs={RedisManagerDBConfig(database=db) for db in (RedisDatabase.LOCKS,)},
        client_name=APP_NAME,
    )


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
