from typing import Final, cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import (
    configure_redis_clients_manager as _sl_configure_redis_clients_manager,
)
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


def configure_redis_clients(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings,
) -> None:
    _sl_configure_redis_clients_manager(
        app_lifespan,
        settings=settings,
        databases_configs=(
            {RedisManagerDBConfig(database=x, decode_responses=False) for x in _BINARY_DBS}
            | {RedisManagerDBConfig(database=x, decode_responses=True) for x in _DECODE_DBS}
        ),
        client_name=APP_NAME,
    )


def get_redis_client(app: FastAPI, database: RedisDatabase) -> RedisClientSDK:
    manager = cast(RedisClientsManager, app.state.redis_clients_manager)
    return manager.client(database)


def get_all_redis_clients(
    app: FastAPI,
) -> dict[RedisDatabase, RedisClientSDK]:
    return {d: get_redis_client(app, d) for d in _ALL_REDIS_DATABASES}
