""" Access to postgres service
 DUMMY!
"""

import logging
from typing import Dict, Optional

import aiopg.sa
import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from fastapi import FastAPI
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from .application import FastAPI, get_settings
from .settings import AppSettings
from .utils.fastapi_shortcuts import add_event_on_shutdown, add_event_on_startup

## from .orm.base import Base



log = logging.getLogger(__name__)


def pg_retry_policy(logger: Optional[logging.Logger] = None) -> Dict:
    """ Retry policy for postgres requests upon failure """
    logger = logger or logging.getLogger(__name__)
    return dict(
        wait=wait_fixed(5),
        stop=stop_after_attempt(20),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )


async def setup_engine(app: FastAPI) -> None:
    settings = get_settings(app)
    engine = await aiopg.sa.create_engine(
        settings.postgres_dsn,
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        minsize=5,
        maxsize=10,
    )
    app.state.engine = engine


async def teardown_engine(app: FastAPI) -> None:
    engine = app.state.engine
    engine.close()
    await engine.wait_closed()


async def get_cnx(app: FastAPI):
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        yield conn


def info(app: FastAPI):
    engine = app.state.engine
    for p in "closed driver dsn freesize maxsize minsize name  size timeout".split():
        print(f"{p} = {getattr(engine, p)}")


def create_tables(settings: AppSettings):
    log.info("creating tables")
    _engine = sa.create_engine(settings.postgres_dsn)
    ## Base.metadata.create_all(bind=engine)


# SETUP ------


async def start_db(app: FastAPI):
    # TODO: tmp disabled
    log.debug("DUMMY: Initializing db in %s", app)

    @retry(**pg_retry_policy(log))
    async def _go():
        await setup_engine(app)

    # if False:
    #    log.info("Creating db tables (testing mode)")
    #    create_tables()


def shutdown_db(app: FastAPI):
    # TODO: tmp disabled
    log.debug("DUMMY: Shutting down db in %s", app)
    # await teardown_engine(app)


def setup_db(app: FastAPI):
    add_event_on_startup(app, start_db)
    add_event_on_shutdown(app, shutdown_db)


__all__ = ("Engine", "ResultProxy", "RowProxy", "SAConnection")
