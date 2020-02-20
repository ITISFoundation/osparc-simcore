""" Access to postgres service

"""
from typing import Optional

import aiopg.sa
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from fastapi import Depends
from sqlalchemy.sql.ddl import CreateTable

from .config import app_context, postgres_dsn
from .orm import DAG, dags


# TODO: idealy context cleanup. This concept here? app-context Dependency?
async def setup_engine() -> Engine:
    engine = await aiopg.sa.create_engine(
        postgres_dsn,
        # unique identifier per app
        application_name=f"{__name__}_{id(app_context)}",
        minsize=5,
        maxsize=10,
    )
    app_context["engine"] = engine

    return engine


async def teardown_engine() -> None:
    engine = app_context["engine"]
    engine.close()
    await engine.wait_closed()


async def create_tables(conn: SAConnection):
    await conn.execute(f"DROP TABLE IF EXISTS {DAG.__tablename__}")
    await conn.execute(CreateTable(dags))


def info(engine: Optional[Engine] = None):
    engine = engine or get_engine()
    props = "closed driver dsn freesize maxsize minsize name  size timeout".split()
    for p in props:
        print(f"{p} = {getattr(engine, p)}")


def get_engine() -> Engine:
    return app_context["engine"]


async def get_cnx(engine: Engine = Depends(get_engine)):
    # TODO: problem here is retries??
    async with engine.acquire() as conn:
        yield conn


__all__ = ("Engine", "ResultProxy", "RowProxy", "SAConnection")
