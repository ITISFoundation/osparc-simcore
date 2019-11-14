import logging

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import create_engine
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from servicelib.aiopg_utils import DBAPIError

from .models import metadata
from .settings import APP_CONFIG_KEY, APP_DB_ENGINE_KEY

log = logging.getLogger(__name__)

THIS_SERVICE_NAME = 'postgres'
DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"

# TODO: move to settings?
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

@retry( wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(log, logging.INFO),
        reraise=True)
async def __create_tables(**params):
    try:
        url = DSN.format(**params) + f"?application_name={__name__}_init"
        sa_engine = sa.create_engine(url)
        metadata.create_all(sa_engine)
    finally:
        sa_engine.dispose()

async def pg_engine(app: web.Application):
    cfg = app[APP_CONFIG_KEY][THIS_SERVICE_NAME]
    params = {key:cfg[key] for key in 'database user password host port'.split()}

    # TODO: set this as optional?
    await __create_tables(**params)

    async with create_engine(application_name=__name__, **params) as engine:
        app[APP_DB_ENGINE_KEY] = engine

        yield

        if engine is not app.get(APP_DB_ENGINE_KEY):
            log.error("app does not hold right db engine")

async def is_service_responsive(app:web.Application):
    """ Returns true if the app can connect to db service

    """
    engine = app[APP_DB_ENGINE_KEY]
    try:
        async with engine.acquire() as conn:
            await conn.execute("SELECT 1 as is_alive")
            log.debug("%s is alive", THIS_SERVICE_NAME)
            return True
    except DBAPIError as err:
        log.debug("%s is NOT responsive: %s", THIS_SERVICE_NAME, err)
        return False

def setup_db(app: web.Application):

    disable_services = app[APP_CONFIG_KEY].get("main", {}).get("disable_services",[])

    if THIS_SERVICE_NAME in disable_services:
        app[APP_DB_ENGINE_KEY] = app[APP_DB_SESSION_KEY] = None
        log.warning("Service '%s' explicitly disabled in config", THIS_SERVICE_NAME)
        return

    app[APP_DB_ENGINE_KEY] = None
    app[APP_DB_SESSION_KEY] = None


    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, THIS_SERVICE_NAME)

    # async connection to db
    app.cleanup_ctx.append(pg_engine)
