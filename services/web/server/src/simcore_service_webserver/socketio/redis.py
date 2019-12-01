import logging

import aioredis
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from .config import APP_CLIENT_REDIS_CLIENT_KEY, CONFIG_SECTION_NAME

log = logging.getLogger(__name__)

THIS_SERVICE_NAME = 'redis'
DSN = "redis://{host}:{port}"


async def redis_client(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    url = DSN.format(**cfg["redis"])
    app[APP_CLIENT_REDIS_CLIENT_KEY] = await aioredis.create_redis_pool(url, encoding="utf-8")
    yield

    app[APP_CLIENT_REDIS_CLIENT_KEY].close()
    await app[APP_CLIENT_REDIS_CLIENT_KEY].wait_closed()

def setup_redis_client(app: web.Application):
    app[APP_CLIENT_REDIS_CLIENT_KEY] = None

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["redis"]["enabled"]:
        return

    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, THIS_SERVICE_NAME)

    app.cleanup_ctx.append(redis_client)
