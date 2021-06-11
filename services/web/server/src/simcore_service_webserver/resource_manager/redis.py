import logging
from typing import Optional

import aioredis
from aiohttp import web
from aioredlock import Aioredlock
from servicelib.application_keys import APP_CONFIG_KEY
from tenacity import AsyncRetrying, before_log, stop_after_attempt, wait_fixed

from .config import (
    APP_CLIENT_REDIS_CLIENT_KEY,
    APP_CLIENT_REDIS_LOCK_MANAGER_KEY,
    CONFIG_SECTION_NAME,
)

log = logging.getLogger(__name__)

THIS_SERVICE_NAME = "redis"
DSN = "redis://{host}:{port}"

retry_upon_init_policy = dict(
    stop=stop_after_attempt(4),
    wait=wait_fixed(1.5),
    before=before_log(log, logging.WARNING),
    reraise=True,
)


async def redis_client(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    url = DSN.format(**cfg["redis"])

    # create redis client
    client: Optional[aioredis.Redis] = None
    async for attempt in AsyncRetrying(**retry_upon_init_policy):
        with attempt:
            client = await aioredis.create_redis_pool(url, encoding="utf-8")
            if not client:
                raise ValueError("Expected aioredis client instance, got {client}")

    # create lock manager
    lock_manager = Aioredlock([url])

    assert client  # nosec
    app[APP_CLIENT_REDIS_CLIENT_KEY] = client

    assert lock_manager  # nosec
    app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY] = lock_manager

    yield

    if client is not app[APP_CLIENT_REDIS_CLIENT_KEY]:
        log.critical("Invalid redis client in app")
    if lock_manager is not app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY]:
        log.critical("Invalid redis lock manager in app")

    # close client
    client.close()
    await client.wait_closed()
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


def get_redis_lock(app: web.Application) -> Aioredlock:
    return app[APP_CLIENT_REDIS_LOCK_MANAGER_KEY]
