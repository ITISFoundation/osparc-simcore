from fastapi import FastAPI
from servicelib.redis import RedisClientsManager
from settings_library.redis import RedisDatabase

from ..core.settings import AppSettings


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: AppSettings = app.state.settings

        app.state.redis_clients_manager = redis_clients_manager = RedisClientsManager(
            databases={
                RedisDatabase.LOCKS,
                RedisDatabase.DISTRIBUTED_IDENTIFIERS,
            },
            settings=settings.REDIS,
        )
        await redis_clients_manager.setup()

    async def on_shutdown() -> None:
        redis_clients_manager: RedisClientsManager = app.state.redis_clients_manager
        await redis_clients_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
