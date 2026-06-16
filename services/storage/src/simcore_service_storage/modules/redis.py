from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from servicelib.fastapi.lifespan_utils import LifespanManager
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase

from .._meta import APP_NAME
from ..core.settings import get_application_settings


@asynccontextmanager
async def _redis_clients_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for Redis clients."""
    app.state.redis_clients_manager = None

    try:
        redis_settings = get_application_settings(app).STORAGE_REDIS

        redis_clients_manager = RedisClientsManager(
            databases_configs={
                RedisManagerDBConfig(database=db)
                for db in (
                    RedisDatabase.LOCKS,
                    RedisDatabase.CELERY_TASKS,
                )
            },
            settings=redis_settings,
            client_name=APP_NAME,
        )
        await redis_clients_manager.setup()
        app.state.redis_clients_manager = redis_clients_manager

        yield
    finally:
        redis_clients_manager: RedisClientsManager = app.state.redis_clients_manager
        if redis_clients_manager:
            await redis_clients_manager.shutdown()


def configure_redis_clients(app_lifespan: LifespanManager) -> None:
    """Configure Redis clients lifespan."""
    app_lifespan.add(_redis_clients_lifespan)


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
