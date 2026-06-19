from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import (
    configure_redis_clients_manager as _sl_configure_redis_clients_manager,
)
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME


def configure_redis_clients_manager(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings | None,
) -> None:
    if settings is None:
        msg = (
            "DIRECTOR_REDIS_CACHE_BACKEND='redis' with DIRECTOR_REGISTRY_CACHING=True requires DIRECTOR_REDIS settings"
        )
        raise RuntimeError(msg)
    _sl_configure_redis_clients_manager(
        app_lifespan,
        settings=settings,
        databases_configs={
            RedisManagerDBConfig(database=db)
            for db in (
                RedisDatabase.LOCKS,
                RedisDatabase.AIOCACHE,
            )
        },
        client_name=APP_NAME,
    )


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
