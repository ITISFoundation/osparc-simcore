

# setup pg engine using aiopg
import aiopg.sa
import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
# Dependency
from fastapi import Depends

from .config import pg_dsn
from .orm.base import Base


def create_tables():
    engine = sa.create_engine(pg_dsn)
    Base.metadata.create_all(bind=engine)


# TODO: hate globals!
app_context = {}


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



def get_engine() -> Engine:
    return app_context["engine"]

async def get_cnx(engine: Engine = Depends(get_engine)):
    # TODO: problem here is retries??
    async with engine.acquire() as conn:
        yield conn



__all__ = (
    'Engine',
    'ResultProxy', 'RowProxy',
    'SAConnection'
)
