""" Interface to manage initialization and operation of a database

    - Exposes async functionality to init and operate a postgress database
    - Database is deployed on a separate service

TODO: async (e.g. in aiopg.sa) or sync(e.g. in comp_backend_api) access? MaG recommends second.
TODO: merge engines!!!
TODO: create tools to diagnose state of db-service
"""
import logging

import aiopg.sa

# FIXME: this is temporary here so database gets properly initialized
from ..comp_backend_api import init_database as _init_db

log = logging.getLogger(__name__)

APP_ENGINE_KEY = 'db_engine'
DB_SERVICE_NAME = 'postgres'

class RecordNotFound(Exception):
    """Requested record in database was not found"""

def is_dbservice_ready(app):
    # TODO: create service states!!!!
    # FIXME: this does not accout for status of the other engine!!!
    try:
        return app[APP_ENGINE_KEY] is not None
    except KeyError:
        return False

async def create_aiopg(app):
    log.debug("creating db engine ... ")

    # FIXME: psycopg2.OperationalError: could not connect to server: Connection refused if db service is not up!
    # FIXME: psycopg2.OperationalError: FATAL:  role "test_aiohttpdemo_user" does not exist
    # TODO: define connection policy for services. What happes if cannot connect to a service? do not have access to its services but
    # what do we do with the server? Retry? stop and exit?

    conf = app["config"][DB_SERVICE_NAME]

    try:
        engine = await aiopg.sa.create_engine(
            database=conf["database"],
            user=conf["user"],
            password=conf["password"],
            host=conf["host"],
            port=conf["port"],
            minsize=conf["minsize"],
            maxsize=conf["maxsize"],
        )

        app[APP_ENGINE_KEY] = engine
        log.debug("db engine created")

    except Exception: #pylint: disable=W0703
        app[APP_ENGINE_KEY] = None
        log.exception("db engine failed")


async def dispose_aiopg(app):
    log.debug("closing db engine ...")

    engine = app[APP_ENGINE_KEY]
    if engine:
        engine.close()
        await engine.wait_closed()

    log.debug("db engine closed")


def setup_db(app):
    log.debug("Setting up %s [service: %s] ...", __name__, DB_SERVICE_NAME)

    disable_services = app["config"].get("app", {}).get("disable_services",[])
    if DB_SERVICE_NAME in disable_services:
        app[APP_ENGINE_KEY] = None
        log.warning("Service '%s' explicitly disabled in config", DB_SERVICE_NAME)
        return

    # FIXME: this create an engine to connect to simcoredb with comp_pipeline and comp_tasks
    app.on_startup.append(_init_db)

    # appends def fun(app) -> coroutines
    app.on_startup.append(create_aiopg)
    app.on_cleanup.append(dispose_aiopg)
