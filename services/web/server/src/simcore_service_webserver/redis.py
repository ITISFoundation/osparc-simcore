import logging
from typing import Final

import redis.asyncio as aioredis
from aiohttp import web
from servicelib.redis import RedisClientSDK, RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

from ._meta import APP_NAME
from .application_keys import APP_SETTINGS_APPKEY
from .application_setup import ModuleCategory, app_setup_func

_logger = logging.getLogger(__name__)


APP_REDIS_CLIENT_KEY: Final = web.AppKey("APP_REDIS_CLIENT_KEY", RedisClientsManager)

# SETTINGS --------------------------------------------------------------------------


def get_plugin_settings(app: web.Application) -> RedisSettings:
    settings: RedisSettings | None = app[APP_SETTINGS_APPKEY].WEBSERVER_REDIS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RedisSettings)  # nosec
    return settings


# EVENTS --------------------------------------------------------------------------
async def setup_redis_client(app: web.Application):
    """

    raises builtin ConnectionError
    """
    redis_settings: RedisSettings = get_plugin_settings(app)
    app[APP_REDIS_CLIENT_KEY] = manager = RedisClientsManager(
        databases_configs={
            RedisManagerDBConfig(database=db)
            for db in (
                RedisDatabase.RESOURCES,
                RedisDatabase.LOCKS,
                RedisDatabase.VALIDATION_CODES,
                RedisDatabase.SCHEDULED_MAINTENANCE,
                RedisDatabase.USER_NOTIFICATIONS,
                RedisDatabase.ANNOUNCEMENTS,
                RedisDatabase.DOCUMENTS,
                RedisDatabase.CELERY_TASKS,
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
    redis_client: RedisClientsManager = app[APP_REDIS_CLIENT_KEY]
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


def get_redis_document_manager_client_sdk(app: web.Application) -> RedisClientSDK:
    return _get_redis_client_sdk(app, RedisDatabase.DOCUMENTS)


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


def get_redis_celery_tasks_client_sdk(app: web.Application) -> RedisClientSDK:
    return _get_redis_client_sdk(app, RedisDatabase.CELERY_TASKS)


# PLUGIN SETUP --------------------------------------------------------------------------


@app_setup_func(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_REDIS", logger=_logger
)
def setup_redis(app: web.Application):
    app.cleanup_ctx.append(setup_redis_client)
