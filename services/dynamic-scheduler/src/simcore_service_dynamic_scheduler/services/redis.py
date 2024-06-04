from typing import Final

from fastapi import FastAPI
from servicelib.redis import (
    RedisClientSDKHealthChecked,
    RedisClientsManager,
    RedisManagerDBConfig,
)
from settings_library.redis import RedisDatabase, RedisSettings

_REDIS_DATABASES: Final[set[RedisDatabase]] = {
    RedisDatabase.DEFERRED_TASKS,
    RedisDatabase.DYNAMIC_SERVICES,
}


def setup_redis(app: FastAPI) -> None:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS

    async def on_startup() -> None:
        app.state.redis_clients_manager = manager = RedisClientsManager(
            {RedisManagerDBConfig(x, decode_responses=False) for x in _REDIS_DATABASES},
            settings,
        )
        await manager.setup()

    async def on_shutdown() -> None:
        manager: RedisClientsManager = app.state.redis_clients_manager
        await manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(
    app: FastAPI, database: RedisDatabase
) -> RedisClientSDKHealthChecked:
    manager: RedisClientsManager = app.state.redis_clients_manager
    return manager.client(database)


def get_all_redis_clients(
    app: FastAPI,
) -> dict[RedisDatabase, RedisClientSDKHealthChecked]:
    return {d: get_redis_client(app, d) for d in _REDIS_DATABASES}
