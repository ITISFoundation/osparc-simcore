

# setup pg engine using aiopg
import asyncio
from typing import Iterator

import aiopg.sa
import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy

from .config import pg_dsn
from .orm import Base


def create_tables():
    engine = sa.create_engine(pg_dsn)
    Base.metadata.create_all(bind=engine)


# TODO: hate globals!
app_context = {}


def get_engine() -> Engine:
    return app_context["engine"]

def info():
    engine = get_engine()
    props = "closed driver dsn freesize maxsize minsize name  size timeout".split()
    for p in props:
        print(f"{p} = {getattr(engine, p)}")


# TODO: idealy context cleanup. This concept here? app-context Dependency?
async def setup_engine() -> None:
    engine = await aiopg.sa.create_engine(pg_dsn, application_name=__name__, minsize=5, maxsize=10)
    app_context['engine'] = engine


async def teardown_engine() -> None:
    engine = app_context['engine']
    engine.close()
    await engine.wait_closed()



__all__ = (
    'Engine',
    'ResultsProxy', 'RowProxy',
    'SAConnection'
)
