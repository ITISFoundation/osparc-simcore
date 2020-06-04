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
        str(settings.postgres_dsn),
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        minsize=5,
        maxsize=10,
    )
    log.debug("Connected to %s", engine.dsn)
    app.state.engine = engine


async def teardown_engine(app: FastAPI) -> None:
    engine = app.state.engine
    engine.close()
    await engine.wait_closed()
    log.debug("Disconnected from %s", engine.dsn)


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
from typing import Callable


def create_start_db_handler(app: FastAPI) -> Callable:
    async def start_db() -> None:
        log.debug("Connenting db ...")

        @retry(**pg_retry_policy(log))
        async def _go():
            await setup_engine(app)

        await _go()

    return start_db


def create_stop_db_handler(app: FastAPI) -> Callable:
    async def stop_db() -> None:
        log.debug("Stopping db ...")
        await teardown_engine(app)

    return stop_db


def setup_db(app: FastAPI):
    app.add_event_handler("startup", create_start_db_handler(app))
    app.add_event_handler("shutdown", create_stop_db_handler(app))


__all__ = ("Engine", "ResultProxy", "RowProxy", "SAConnection")
