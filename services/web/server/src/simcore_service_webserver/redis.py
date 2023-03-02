import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from settings_library.redis import RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ._constants import APP_SETTINGS_KEY
from .redis_constants import (
    APP_CLIENT_REDIS_CLIENT_KEY,
    APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY,
    APP_CLIENT_REDIS_SCHEDULED_MAINTENANCE_CLIENT_KEY,
    APP_CLIENT_REDIS_VALIDATION_CODE_CLIENT_KEY,
    APP_CLIENT_REDIS_USER_NOTIFICATIONS_CLIENT_KEY,
)

log = logging.getLogger(__name__)

_MINUTE = 60
_WAIT_SECS = 2

# SETTINGS --------------------------------------------------------------------------


def get_plugin_settings(app: web.Application) -> RedisSettings:
    settings: Optional[RedisSettings] = app[APP_SETTINGS_KEY].WEBSERVER_REDIS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RedisSettings)  # nosec
    return settings


# EVENTS --------------------------------------------------------------------------
async def setup_redis_client(app: web.Application):
    """

    raises builtin ConnectionError
    """
    redis_settings: RedisSettings = get_plugin_settings(app)

    async def _create_client(address: str) -> aioredis.Redis:
        """raises ConnectionError if fails"""
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(1 * _MINUTE),
            wait=wait_fixed(_WAIT_SECS),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                client = aioredis.from_url(
                    address, encoding="utf-8", decode_responses=True
                )
                if not await client.ping():
                    await client.close(close_connection_pool=True)
                    raise ConnectionError(f"Connection to {address!r} failed")
                log.info(
                    "Connection to %s succeeded with %s [%s]",
                    f"redis at {address=}",
                    f"{client=}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
            assert client  # nosec
            return client

    REDIS_DSN_MAP = {
        APP_CLIENT_REDIS_CLIENT_KEY: redis_settings.dsn_resources,
        APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY: redis_settings.dsn_locks,
        APP_CLIENT_REDIS_VALIDATION_CODE_CLIENT_KEY: redis_settings.dsn_validation_codes,
        APP_CLIENT_REDIS_SCHEDULED_MAINTENANCE_CLIENT_KEY: redis_settings.dsn_scheduled_maintenance,
        APP_CLIENT_REDIS_USER_NOTIFICATIONS_CLIENT_KEY: redis_settings.dsn_notifications,
    }

    for app_key, dsn in REDIS_DSN_MAP.items():
        assert app.get(app_key) is None  # nosec
        app[app_key] = await _create_client(dsn)

    yield

    for app_key in REDIS_DSN_MAP.keys():
        if redis_client := app.get(app_key):
            await redis_client.close(close_connection_pool=True)


def _get_redis_client(app: web.Application, app_key: str) -> aioredis.Redis:
    redis_client = app[app_key]
    assert redis_client is not None, f"redis plugin was not init for {app_key}"  # nosec
    return redis_client


def get_redis_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, APP_CLIENT_REDIS_CLIENT_KEY)


def get_redis_lock_manager_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY)


def get_redis_validation_code_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, APP_CLIENT_REDIS_VALIDATION_CODE_CLIENT_KEY)


def get_redis_scheduled_maintenance_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, APP_CLIENT_REDIS_SCHEDULED_MAINTENANCE_CLIENT_KEY)


def get_redis_notifications_client(app: web.Application) -> aioredis.Redis:
    return _get_redis_client(app, APP_CLIENT_REDIS_USER_NOTIFICATIONS_CLIENT_KEY)


# PLUGIN SETUP --------------------------------------------------------------------------


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_REDIS", logger=log
)
def setup_redis(app: web.Application):
    app.cleanup_ctx.append(setup_redis_client)
