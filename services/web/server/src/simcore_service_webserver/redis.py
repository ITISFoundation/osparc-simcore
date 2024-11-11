import logging

import redis.asyncio as aioredis
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.redis import RedisClientSDK, RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

from ._constants import APP_SETTINGS_KEY
from ._meta import APP_NAME

_logger = logging.getLogger(__name__)


_APP_REDIS_CLIENTS_MANAGER = f"{__name__}.redis_clients_manager"


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
    app[_APP_REDIS_CLIENTS_MANAGER] = manager = RedisClientsManager(
        databases_configs={
            RedisManagerDBConfig(db)
            for db in (
                RedisDatabase.RESOURCES,
                RedisDatabase.LOCKS,
                RedisDatabase.VALIDATION_CODES,
                RedisDatabase.SCHEDULED_MAINTENANCE,
                RedisDatabase.USER_NOTIFICATIONS,
                RedisDatabase.ANNOUNCEMENTS,
            )
        },
        settings=redis_settings,
        client_name=APP_NAME,
    )

    await manager.setup()

    yield

    await manager.shutdown()


# UTILS --------------------------------------------------------------------------


def _get_redis_client_sdk(
    app: web.Application, database: RedisDatabase
) -> RedisClientSDK:
    redis_client: RedisClientsManager = app[_APP_REDIS_CLIENTS_MANAGER]
    return redis_client.client(database)


def get_redis_resources_client(app: web.Application) -> aioredis.Redis:
    redis_client: aioredis.Redis = _get_redis_client_sdk(
        app, RedisDatabase.RESOURCES
    ).redis
    return redis_client


def get_redis_lock_manager_client(app: web.Application) -> aioredis.Redis:
    redis_client: aioredis.Redis = _get_redis_client_sdk(app, RedisDatabase.LOCKS).redis
    return redis_client


def get_redis_lock_manager_client_sdk(app: web.Application) -> RedisClientSDK:
    return _get_redis_client_sdk(app, RedisDatabase.LOCKS)


def get_redis_validation_code_client(app: web.Application) -> aioredis.Redis:
    redis_client: aioredis.Redis = _get_redis_client_sdk(
        app, RedisDatabase.VALIDATION_CODES
    ).redis
    return redis_client


def get_redis_scheduled_maintenance_client(app: web.Application) -> aioredis.Redis:
    redis_client: aioredis.Redis = _get_redis_client_sdk(
        app, RedisDatabase.SCHEDULED_MAINTENANCE
    ).redis
    return redis_client


def get_redis_user_notifications_client(app: web.Application) -> aioredis.Redis:
    redis_client: aioredis.Redis = _get_redis_client_sdk(
        app, RedisDatabase.USER_NOTIFICATIONS
    ).redis
    return redis_client


def get_redis_announcements_client(app: web.Application) -> aioredis.Redis:
    redis_client: aioredis.Redis = _get_redis_client_sdk(
        app, RedisDatabase.ANNOUNCEMENTS
    ).redis
    return redis_client


# PLUGIN SETUP --------------------------------------------------------------------------


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_REDIS", logger=_logger
)
def setup_redis(app: web.Application):
    app.cleanup_ctx.append(setup_redis_client)
