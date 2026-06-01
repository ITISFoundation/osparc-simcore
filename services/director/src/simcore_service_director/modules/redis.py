from typing import cast

from fastapi import FastAPI
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase

from .._meta import APP_NAME
from ..core.settings import ApplicationSettings, get_application_settings


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = get_application_settings(app)

        app.state.redis_clients_manager = None
        if not settings.DIRECTOR_REGISTRY_CACHING or settings.DIRECTOR_REDIS_CACHE_BACKEND != "redis":
            return

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

    async def on_shutdown() -> None:
        redis_clients_manager: RedisClientsManager | None = app.state.redis_clients_manager
        if redis_clients_manager:
            await redis_clients_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
