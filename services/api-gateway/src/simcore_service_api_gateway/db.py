""" Access to postgres service

"""
import logging
from typing import Dict, Optional

import aiopg.sa
import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from fastapi import FastAPI
from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_fixed

from .config import app_context, is_testing_enabled, postgres_dsn
from .orm.base import Base

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


# TODO: idealy context cleanup. This concept here? app-context Dependency?
async def setup_engine() -> None:
    engine = await aiopg.sa.create_engine(
        postgres_dsn,
        application_name=f"{__name__}_{id(app_context)}",  # unique identifier per app
        minsize=5,
        maxsize=10,
    )
    app_context["engine"] = engine


async def teardown_engine() -> None:
    engine = app_context["engine"]
    engine.close()
    await engine.wait_closed()


def get_engine() -> Engine:
    return app_context["engine"]


async def get_cnx():
    # TODO: problem here is retries??
    async with get_engine().acquire() as conn:
        yield conn


def info():
    engine = get_engine()
    for p in "closed driver dsn freesize maxsize minsize name  size timeout".split():
        print(f"{p} = {getattr(engine, p)}")


def create_tables():
    engine = sa.create_engine(postgres_dsn)
    Base.metadata.create_all(bind=engine)


# SETUP ------


async def start_db():
    log.info("Initializing db")

    # FIXME: do async
    for attempt in Retrying(**pg_retry_policy(log)):
        with attempt:
            await setup_engine()

    if is_testing_enabled:
        log.info("Creating db tables (testing mode)")
        create_tables()


async def shutdown_db():
    log.info("Shutting down db")
    await teardown_engine()


def setup_db(app: FastAPI):

    app.router.add_event_handler("startup", start_db)
    app.router.add_event_handler("shutdown", shutdown_db)


__all__ = ("Engine", "ResultProxy", "RowProxy", "SAConnection")
