""" database submodule associated to the postgres uservice


FIXME: _init_db is temporary here so database gets properly initialized
"""

import logging

from aiohttp import web
from aiopg.sa import create_engine

from servicelib.aiopg_utils import DBAPIError, create_all, drop_all

from .application_keys import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY,
                               APP_DB_SESSION_KEY)
from .comp_backend_api import init_database as _init_db



THIS_SERVICE_NAME = 'postgres'
DNS = "postgresql://{user}:{password}@{host}:{port}/{database}" # TODO: in sync with config

# TODO: move to settings? or register?
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30



log = logging.getLogger(__name__)


async def pg_engine(app: web.Application):
    cfg = app[APP_CONFIG_KEY][THIS_SERVICE_NAME]

    engine = None
    try:
        params = {k:cfg[k] for k in 'database user password host port minsize maxsize'.split()}
        engine = await create_engine(**params)
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


async def is_service_responsive(app: web.Application):
    """ Returns true if the app can connect to db service

    """
    # FIXME: this does not accout for status of the other engine!!!
    try:
        engine = app[APP_DB_ENGINE_KEY]
        assert engine is not None
        async with engine.acquire():
            log.debug("%s is responsive", THIS_SERVICE_NAME)
            return True
    except (KeyError, AssertionError, DBAPIError) as err:
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
    'is_service_responsive'
)
