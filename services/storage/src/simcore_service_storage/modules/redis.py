from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import configure_redis_clients_manager
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME


def configure_redis_clients(
    app_lifespan: LifespanManager,
    *,
    settings: RedisSettings,
) -> None:
    configure_redis_clients_manager(
        app_lifespan,
        settings=settings,
        databases_configs={
            RedisManagerDBConfig(database=db)
            for db in (
                RedisDatabase.LOCKS,
                RedisDatabase.CELERY_TASKS,
            )
        },
        client_name=APP_NAME,
    )


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
