import logging

import redis.asyncio as aioredis
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.redis import RedisClientSDK, RedisClientsManager
from settings_library.redis import RedisDatabase, RedisSettings

from ._constants import APP_SETTINGS_KEY

log = logging.getLogger(__name__)


APP_REDIS_CLIENTS_MANAGER = f"{__name__}.redis_clients_manager"


# SETTINGS --------------------------------------------------------------------------


def get_plugin_settings(app: web.Application) -> RedisSettings:
    settings: RedisSettings | None = app[APP_SETTINGS_KEY].WEBSERVER_REDIS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RedisSettings)  # nosec
    return settings


# EVENTS --------------------------------------------------------------------------
async def setup_redis_client(app: web.Application):
    """

    raises builtin ConnectionError
    """
    redis_settings: RedisSettings = get_plugin_settings(app)
    app[APP_REDIS_CLIENTS_MANAGER] = manager = RedisClientsManager(
        databases={
            RedisDatabase.RESOURCES,
            RedisDatabase.LOCKS,
            RedisDatabase.VALIDATION_CODES,
            RedisDatabase.SCHEDULED_MAINTENANCE,
            RedisDatabase.USER_NOTIFICATIONS,
        },
        settings=redis_settings,
    )

    await manager.setup()

    yield

    await manager.shutdown()


def _get_redis_client(app: web.Application, database: RedisDatabase) -> RedisClientSDK:
    redis_client: RedisClientsManager = app[APP_REDIS_CLIENTS_MANAGER]
    if redis_client is None:
        raise RuntimeError(f"redis plugin was not init for {APP_REDIS_CLIENTS_MANAGER}")
    return redis_client.client(database)


def get_redis_resources_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, RedisDatabase.RESOURCES).redis


def get_redis_lock_manager_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, RedisDatabase.LOCKS).redis


def get_redis_lock_manager_client_sdk(app: web.Application) -> RedisClientSDK:
    return _get_redis_client(app, RedisDatabase.LOCKS)


def get_redis_validation_code_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, RedisDatabase.VALIDATION_CODES).redis


def get_redis_scheduled_maintenance_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, RedisDatabase.SCHEDULED_MAINTENANCE).redis


def get_redis_user_notifications_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, RedisDatabase.USER_NOTIFICATIONS).redis


# PLUGIN SETUP --------------------------------------------------------------------------


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_REDIS", logger=log
)
def setup_redis(app: web.Application):
    app.cleanup_ctx.append(setup_redis_client)
