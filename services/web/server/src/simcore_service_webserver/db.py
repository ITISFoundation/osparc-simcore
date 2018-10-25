""" database submodule associated to the postgres uservice


FIXME: _init_db is temporary here so database gets properly initialized
"""

import logging

import aiopg.sa
from aiohttp import web
from aiopg.sa import create_engine
from tenacity import retry, stop_after_attempt, wait_fixed, before_sleep_log

from servicelib.aiopg_utils import DBAPIError, create_all, drop_all

from .application_keys import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY,
                               APP_DB_SESSION_KEY)
from .comp_backend_api import init_database as _init_db


# SETTINGS ----------------------------------------------------
THIS_SERVICE_NAME = 'postgres'
DNS = "postgresql://{user}:{password}@{host}:{port}/{database}" # TODO: in sync with config

RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30
# --------------------------------------------------------------


log = logging.getLogger(__name__)


@retry( wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(log, logging.DEBUG) )
async def __create_tables(engine: aiopg.sa.engine.Engine):
    from .db_models import metadata as tables_metadata
    create_all(engine, tables_metadata, checkfirst=True)

async def pg_engine(app: web.Application):

    engine = None
    try:
        cfg = app[APP_CONFIG_KEY][THIS_SERVICE_NAME]
        params = {k:cfg[k] for k in 'database user password host port minsize maxsize'.split()}
        engine = await create_engine(**params)

        # TODO: get keys from __name__ (see notes in servicelib.application_keys)
        if app[APP_CONFIG_KEY]["main"]["db"]["init_tables"]:
            __create_tables(engine)

    except DBAPIError:
        log.exception("Could not create engine")

    session = None
    app[APP_DB_ENGINE_KEY] = engine
    app[APP_DB_SESSION_KEY] = session # placeholder for session (if needed)

    yield

    session = app.get(APP_DB_SESSION_KEY)
    if session:
        session.close()

    engine = app.get(APP_DB_ENGINE_KEY)
    if engine:
        engine.close()
        await engine.wait_closed()


def is_service_enabled(app: web.Application):
    return app.get(APP_DB_ENGINE_KEY) is not None


async def is_service_responsive(app:web.Application):
    """ Returns true if the app can connect to db service

    """
    if not is_service_enabled(app):
        return False

    engine = app[APP_DB_ENGINE_KEY]
    try:
        async with engine.acquire() as conn:
            await conn.execute("SELECT 1 as is_alive")
            log.debug("%s is alive", THIS_SERVICE_NAME)
            return True
    except DBAPIError as err:
        log.debug("%s is NOT responsive: %s", THIS_SERVICE_NAME, err)
        return False

def setup(app: web.Application):

    disable_services = app[APP_CONFIG_KEY]["main"]["disable_services"]

    if THIS_SERVICE_NAME in disable_services:
        app[APP_DB_ENGINE_KEY] = app[APP_DB_SESSION_KEY] = None
        log.warning("Service '%s' explicitly disabled in cfgig", THIS_SERVICE_NAME)
        return

    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, THIS_SERVICE_NAME)

    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None
    app[APP_DB_SESSION_KEY] = None

    # async connection to db
    app.on_startup.append(_init_db) # TODO: review how is this disposed
    app.cleanup_ctx.append(pg_engine)


# alias ---
setup_db = setup
create_all = create_all
drop_all = drop_all

__all__ = (
    'setup_db',
    'is_service_enabled'
)
