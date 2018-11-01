import logging
from .settings import APP_CONFIG_KEY
from aiopg.sa import create_engine
from aiohttp import web

from .settings import APP_DB_ENGINE_KEY, APP_DB_SESSION_KEY

log = logging.getLogger(__name__)

_SERVICE_NAME = 'postgres'


# TODO: move to settings?
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

async def pg_engine(app: web.Application):
    cfg = app[APP_CONFIG_KEY]["postgres"]
    engine = None
    try:
        engine = await create_engine(user=cfg["user"],
            database=cfg["database"],
            host=cfg["host"],
            password=["password"])
    except Exception: # pylint: disable=W0703
        log.exception("Could not create engine")

    session = None
    app[APP_DB_ENGINE_KEY] = engine
    app[APP_DB_SESSION_KEY] = session

    yield

    session = app.get(APP_DB_SESSION_KEY)
    if session:
        session.close()

    engine = app.get(APP_DB_ENGINE_KEY)
    if engine:
        engine.close()
        await engine.wait_closed()



def setup_db(app: web.Application):

    disable_services = app[APP_CONFIG_KEY].get("main", {}).get("disable_services",[])

    if _SERVICE_NAME in disable_services:
        app[APP_DB_ENGINE_KEY] = app[APP_DB_SESSION_KEY] = None
        log.warning("Service '%s' explicitly disabled in config", _SERVICE_NAME)
        return


    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, _SERVICE_NAME)

    # async connection to db
    app.cleanup_ctx.append(pg_engine)
