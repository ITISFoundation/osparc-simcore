
import logging

from aiohttp import web
from aiopg.sa import create_engine

from .application_keys import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY,
                               APP_DB_SESSION_KEY)
from .comp_backend_api import init_database as _init_db

# FIXME: _init_db is temporary here so database gets properly initialized

THIS_SERVICE_NAME = 'postgres'
# TODO: move to settings? or register?
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

# TODO: in sync with config
DNS = "postgresql://{user}:{password}@{host}:{port}/{database}"

log = logging.getLogger(__name__)


async def pg_engine(app: web.Application):
    cfg = app[APP_CONFIG_KEY][THIS_SERVICE_NAME]

    engine = None
    try:
        # TODO: too verbose. need only cfg and keys, then unwrap!
        engine = await create_engine(
            database=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            host=cfg["host"],
            port=cfg["port"],
            minsize=cfg["minsize"],
            maxsize=cfg["maxsize"],
        )
    except Exception: # pylint: disable=W0703
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

def setup_db(app: web.Application):

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


# helpers -------------------------------------
def is_service_ready(app: web.Application):
    # TODO: create service states!!!!
    # FIXME: this does not accout for status of the other engine!!!
    try:
        return app[APP_DB_ENGINE_KEY] is not None
    except KeyError:
        return False
