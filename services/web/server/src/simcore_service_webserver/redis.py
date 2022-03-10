import json
import logging
from typing import Optional

import aioredis
from aiohttp import web
from aioredlock import Aioredlock
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
    APP_CLIENT_REDIS_LOCK_MANAGER_KEY,
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
    redis_settings: RedisSettings = get_plugin_settings(app)

    async def _create_client(address: str) -> aioredis.Redis:
        client: Optional[aioredis.Redis] = None

        async for attempt in AsyncRetrying(
            stop=stop_after_delay(1 * _MINUTE),
            wait=wait_fixed(_WAIT_SECS),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                client = await aioredis.create_redis_pool(address, encoding="utf-8")
                log.info(
                    "Connection to %s succeeded with %s [%s]",
                    f"redis at {address=}",
                    f"{client=}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
        assert client  # nosec
        return client

    origin_url = f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}"
    log.info(
        "Connecting to redis at %s",
        f"{origin_url=}",
    )
    app[APP_CLIENT_REDIS_CLIENT_KEY] = client = await _create_client(origin_url)
    assert client  # nosec

    # TODO: use RedisDsn.build(**redis_settings.build_kwargs()) via a Mixin?
    # create lock manager but use DB 1
    lock_db_url = origin_url + "/1"

    # create a client for it as well
    app[
        APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY
    ] = client_lock_db = await _create_client(lock_db_url)
    assert client_lock_db  # nosec

    app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY] = lock_manager = Aioredlock([lock_db_url])  # type: ignore
    assert lock_manager  # nosec

    yield

    if client is not app[APP_CLIENT_REDIS_CLIENT_KEY]:
        log.critical("Invalid redis client in app")
    if client_lock_db is not app[APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY]:
        log.critical("Invalid redis client for lock db in app")
    if lock_manager is not app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY]:
        log.critical("Invalid redis lock manager in app")

    # close clients
    client.close()
    await client.wait_closed()
    client_lock_db.close()
    await client_lock_db.wait_closed()
    # delete lock manager
    await lock_manager.destroy()


def get_redis_client(app: web.Application) -> aioredis.Redis:
    client = app[APP_CLIENT_REDIS_CLIENT_KEY]
    assert client is not None, "redis plugin was not init"  # nosec
    return client


def get_redis_lock_manager(app: web.Application) -> Aioredlock:
    return app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY]


def get_redis_lock_manager_client(app: web.Application) -> aioredis.Redis:
    return app[APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY]


# PLUGIN SETUP --------------------------------------------------------------------------


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_REDIS", logger=log
)
def setup_redis(app: web.Application):
    app.cleanup_ctx.append(setup_redis_client)
