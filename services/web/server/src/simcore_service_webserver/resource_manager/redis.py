import json
import logging
from typing import Optional

import aioredis
from aiohttp import web
from aioredlock import Aioredlock
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .config import (
    APP_CLIENT_REDIS_CLIENT_KEY,
    APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY,
    APP_CLIENT_REDIS_LOCK_MANAGER_KEY,
    CONFIG_SECTION_NAME,
)

log = logging.getLogger(__name__)

THIS_SERVICE_NAME = "redis"
DSN = "redis://{host}:{port}"
_MINUTE = 60
_WAIT_SECS = 2


async def redis_client(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    endpoint = DSN.format(**cfg["redis"])

    async def create_client(url) -> aioredis.Redis:
        # create redis client
        client: Optional[aioredis.Redis] = None
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(1 * _MINUTE),
            wait=wait_fixed(_WAIT_SECS),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                client = await aioredis.create_redis_pool(url, encoding="utf-8")
                if not client:
                    raise ValueError("Expected aioredis client instance, got {client}")
                log.info(
                    "Connection to %s succeeded [%s]",
                    f"redis at {endpoint=}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
        assert client  # no sec
        return client

    log.info(
        "Connecting to %s",
        f"redis at {endpoint=}",
    )
    app[APP_CLIENT_REDIS_CLIENT_KEY] = client = await create_client(endpoint)
    assert client  # nosec

    # create lock manager but use DB 1
    lock_db_url = endpoint + "/1"
    # create a client for it as well
    app[
        APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY
    ] = client_lock_db = await create_client(lock_db_url)
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


def setup_redis_client(app: web.Application):
    app[APP_CLIENT_REDIS_CLIENT_KEY] = None

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["redis"]["enabled"]:
        return

    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, THIS_SERVICE_NAME)

    app.cleanup_ctx.append(redis_client)


def get_redis_client(app: web.Application) -> aioredis.Redis:
    return app[APP_CLIENT_REDIS_CLIENT_KEY]


def get_redis_lock_manager(app: web.Application) -> Aioredlock:
    return app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY]


def get_redis_lock_manager_client(app: web.Application) -> aioredis.Redis:
    return app[APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY]
