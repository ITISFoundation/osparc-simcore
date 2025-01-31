from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def lifespan_redis(app: FastAPI) -> AsyncIterator[None]:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS

    app.state.redis_clients_manager = manager = RedisClientsManager(
        {RedisManagerDBConfig(database=x, decode_responses=False) for x in _BINARY_DBS}
        | {
            RedisManagerDBConfig(database=x, decode_responses=True) for x in _DECODE_DBS
        },
        settings,
        client_name=APP_NAME,
    )
    await manager.setup()

    yield

    await manager.shutdown()


def get_redis_client(app: FastAPI, database: RedisDatabase) -> RedisClientSDK:
    manager: RedisClientsManager = app.state.redis_clients_manager
    return manager.client(database)


def get_all_redis_clients(
    app: FastAPI,
) -> dict[RedisDatabase, RedisClientSDK]:
    return {d: get_redis_client(app, d) for d in _ALL_REDIS_DATABASES}
