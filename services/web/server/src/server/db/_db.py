""" Interface to manage initialization and operation of a database

    - Exposes async functionality to init and operate a postgress database
    - Database is deployed on a separate service

TODO: async (e.g. in aiopg.sa) or sync(e.g. in comp_backend_api) access? MaG recommends second.
"""
import logging

import aiopg.sa

# FIXME: this is temporary here so database gets properly initialized
# FIXME:
from ..comp_backend_api import init_database as _init_db

_LOGGER = logging.getLogger(__name__)

class RecordNotFound(Exception):
    """Requested record in database was not found"""

async def create_aiopg(app):
    _LOGGER.debug("creating db engine ... ")

    # FIXME: psycopg2.OperationalError: could not connect to server: Connection refused if db service is not up!
    # FIXME: psycopg2.OperationalError: FATAL:  role "test_aiohttpdemo_user" does not exist
    # TODO: define connection policy for services. What happes if cannot connect to a service? do not have access to its services but
    # what do we do with the server? Retry? stop and exit?

    conf = app["config"]["postgres"]
    engine = await aiopg.sa.create_engine(
        database=conf["database"],
        user=conf["user"],
        password=conf["password"],
        host=conf["host"],
        port=conf["port"],
        minsize=conf["minsize"],
        maxsize=conf["maxsize"],
    )

    app["db_engine"] = engine
    _LOGGER.debug("db engine created")


async def dispose_aiopg(app):
    _LOGGER.debug("closing db engine ...")

    app["db_engine"].close()
    await app["db_engine"].wait_closed()

    _LOGGER.debug("db engine closed")


def setup_db(app):
    _LOGGER.debug("Setting up %s ...", __name__)

    # FIXME: this create an engine to connect to simcoredb with comp_pipeline and comp_tasks
    app.on_startup.append(_init_db)

    # appends def fun(app) -> coroutines
    app.on_startup.append(create_aiopg)
    app.on_cleanup.append(dispose_aiopg)
