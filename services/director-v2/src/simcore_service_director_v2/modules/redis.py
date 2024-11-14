from typing import cast

from fastapi import FastAPI
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase

from .._meta import APP_NAME
from ..core.settings import AppSettings


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: AppSettings = app.state.settings

        app.state.redis_clients_manager = redis_clients_manager = RedisClientsManager(
            databases_configs={
                RedisManagerDBConfig(db)
                for db in (
                    RedisDatabase.LOCKS,
                    RedisDatabase.DISTRIBUTED_IDENTIFIERS,
                )
            },
            settings=settings.REDIS,
            client_name=APP_NAME,
        )
        await redis_clients_manager.setup()

    async def on_shutdown() -> None:
        redis_clients_manager: RedisClientsManager = app.state.redis_clients_manager
        await redis_clients_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client_manager(app: FastAPI) -> RedisClientsManager:
    return cast(RedisClientsManager, app.state.redis_clients_manager)
