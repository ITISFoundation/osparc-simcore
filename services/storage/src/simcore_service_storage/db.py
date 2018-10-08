import logging
from .settings import CONFIG_KEY
from aiopg.sa import create_engine

log = logging.getLogger(__name__)

DB_SERVICE_NAME = 'postgres'

# app[key]
DB_ENGINE_KEY  = 'db_engine'
DB_SESSION_KEY = 'db_session'

RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

async def pg_engine(app):
    cfg = app[CONFIG_KEY]["postgres"]
    engine = None
    try:
        engine = await create_engine(user=cfg["user"],
            database=cfg["database"],
            host=cfg["host"],
            password=["password"])
    except Exception: # pylint: disable=W0703
        log.exception("Could not create engine")

    session = None
    app[DB_ENGINE_KEY] = engine
    app[DB_SESSION_KEY] = session

    yield

    session = app.get(DB_SESSION_KEY)
    if session:
        session.close()

    engine = app.get(DB_ENGINE_KEY)
    if engine:
        engine.close()
        await engine.wait_closed()

def setup_db(app):
    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, DB_SERVICE_NAME)

    # async connection to db
    app.cleanup_ctx.append(pg_engine)
