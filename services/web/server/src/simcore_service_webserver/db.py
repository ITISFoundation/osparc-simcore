""" database submodule associated to the postgres uservice


FIXME: _init_db is temporary here so database gets properly initialized
"""

import logging

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import create_engine
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from servicelib.aiopg_utils import DBAPIError
from servicelib.application_keys import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY,
                                         APP_DB_SESSION_KEY)

# from .computation_api import init_database as _init_db
from .db_config import CONFIG_SECTION_NAME
from .db_models import metadata

# SETTINGS ----------------------------------------------------
THIS_MODULE_NAME  = __name__.split(".")[-1]
THIS_SERVICE_NAME = 'postgres'
DSN = "postgresql://{user}:{password}@{host}:{port}/{database}" # Data Source Name. TODO: sync with config

RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30
# --------------------------------------------------------------


log = logging.getLogger(__name__)


@retry( wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(log, logging.INFO) )
async def __create_tables(**params):
    # TODO: move _init_db.metadata here!?
    sa_engine = sa.create_engine(DSN.format(**params))
    metadata.create_all(sa_engine)

async def pg_engine(app: web.Application):
    engine = None
    try:
        cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
        params = {k:cfg["postgres"][k] for k in 'database user password host port minsize maxsize'.split()}
        engine = await create_engine(**params)

        # TODO: get keys from __name__ (see notes in servicelib.application_keys)
        if cfg.get("init_tables"):
            await __create_tables(**params)

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
    log.debug("Setting up %s [service: %s] ...", __name__, THIS_SERVICE_NAME)

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["enabled"]:
        app[APP_DB_ENGINE_KEY] = app[APP_DB_SESSION_KEY] = None
        log.warning("Service '%s' explicitly disabled in config", THIS_SERVICE_NAME)
        return

    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None
    app[APP_DB_SESSION_KEY] = None

    # async connection to db
    # app.on_startup.append(_init_db) # TODO: review how is this disposed
    app.cleanup_ctx.append(pg_engine)


# alias ---
setup_db = setup

__all__ = (
    'setup_db',
    'is_service_enabled'
)
