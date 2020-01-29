import logging

import aioredis
from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from tenacity import Retrying, stop_after_attempt, wait_random, before_log

from .config import APP_CLIENT_REDIS_CLIENT_KEY, CONFIG_SECTION_NAME

log = logging.getLogger(__name__)

THIS_SERVICE_NAME = 'redis'
DSN = "redis://{host}:{port}"

retry_policy = dict(
    stop=stop_after_attempt(3),
    wait=wait_random(min=1, max=2),
    before=before_log(log, logging.ERROR))


async def redis_client(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    url = DSN.format(**cfg["redis"])

    for attempt in Retrying(**retry_policy):
        with attempt:
            client = await aioredis.create_redis_pool(url, encoding="utf-8")

    app[APP_CLIENT_REDIS_CLIENT_KEY] = client

    yield

    if client is not app[APP_CLIENT_REDIS_CLIENT_KEY]:
        log.critical("Invalid redis client in app")

    client.close()
    await client.wait_closed()

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
