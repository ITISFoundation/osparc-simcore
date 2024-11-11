from typing import Final

from fastapi import FastAPI
from servicelib.redis import RedisClientSDK, RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME

_DECODE_DBS: Final[set[RedisDatabase]] = {
    RedisDatabase.LOCKS,
}

_BINARY_DBS: Final[set[RedisDatabase]] = {
    RedisDatabase.DEFERRED_TASKS,
    RedisDatabase.DYNAMIC_SERVICES,
}

_ALL_REDIS_DATABASES: Final[set[RedisDatabase]] = _DECODE_DBS | _BINARY_DBS


def setup_redis(app: FastAPI) -> None:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS

    async def on_startup() -> None:
        app.state.redis_clients_manager = manager = RedisClientsManager(
            {RedisManagerDBConfig(x, decode_responses=False) for x in _BINARY_DBS}
            | {RedisManagerDBConfig(x, decode_responses=True) for x in _DECODE_DBS},
            settings,
            client_name=APP_NAME,
        )
        await manager.setup()

    async def on_shutdown() -> None:
        manager: RedisClientsManager = app.state.redis_clients_manager
        await manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(app: FastAPI, database: RedisDatabase) -> RedisClientSDK:
    manager: RedisClientsManager = app.state.redis_clients_manager
    return manager.client(database)


def get_all_redis_clients(
    app: FastAPI,
) -> dict[RedisDatabase, RedisClientSDK]:
    return {d: get_redis_client(app, d) for d in _ALL_REDIS_DATABASES}
