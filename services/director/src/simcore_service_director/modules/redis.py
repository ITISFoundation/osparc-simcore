from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase

from .._meta import APP_NAME
from ..core.settings import ApplicationSettings, get_application_settings


async def _redis_clients_manager_lifespan(app: FastAPI) -> AsyncIterator[State]:
    redis_clients_manager: RedisClientsManager | None = None
    try:
        settings: ApplicationSettings = get_application_settings(app)
        redis_settings = settings.DIRECTOR_REDIS
        if redis_settings is None:
            msg = (
                "DIRECTOR_REDIS_CACHE_BACKEND='redis' with DIRECTOR_REGISTRY_CACHING=True "
                "requires DIRECTOR_REDIS settings"
            )
            raise RuntimeError(msg)
        app.state.redis_clients_manager = redis_clients_manager = RedisClientsManager(
            databases_configs={
                RedisManagerDBConfig(database=db)
                for db in (
                    RedisDatabase.LOCKS,
                    RedisDatabase.AIOCACHE,
                )
            },
            settings=redis_settings,
            client_name=APP_NAME,
        )
        await redis_clients_manager.setup()
        yield {}
    finally:
        if redis_clients_manager is not None:
            await redis_clients_manager.shutdown()


def configure_redis_clients_manager(
    app_lifespan: LifespanManager[FastAPI],
) -> None:
    app_lifespan.add(_redis_clients_manager_lifespan)


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
