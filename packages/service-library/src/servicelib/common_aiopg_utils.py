""" A service-independent module with aiopg utils

    This module was necessary because simcore-sdk (an aiohttp-independent package) still needs some
    of the helpers here.
"""
from dataclasses import asdict, dataclass
from typing import Optional

import sqlalchemy as sa
from aiopg.sa import create_engine

DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"


@dataclass
class DataSourceName:
    user: str
    password: str
    database: str
    host: str = "127.0.0.1"
    port: int = 5432

    # Attributes about the caller
    application_name: Optional[str] = None

    def to_uri(self, with_query=False) -> str:
        uri = DSN.format(**asdict(self))
        if with_query and self.application_name:
            uri += f"?application_name={self.application_name}"
        return uri


def create_pg_engine(
    dsn: DataSourceName, minsize: int = 1, maxsize: int = 4, **pool_kwargs
):
    """Adapts the arguments of aiopg.sa.create_engine

    Returns a coroutine that is awaitable, i.e.

    async with create_pg_engine as engine:
        assert not engine.closed

    assert engine.closed
    """
    aiopg_engine_context = create_engine(
        dsn.to_uri(),
        application_name=dsn.application_name,
        minsize=minsize,
        maxsize=maxsize,
        **pool_kwargs,
    )
    return aiopg_engine_context


def is_postgres_responsive(dsn: DataSourceName) -> bool:
    # NOTE: keep for tests
    engine = conn = None
    try:
        engine = sa.create_engine(dsn.to_uri())
        conn = engine.connect()
    except sa.exc.OperationalError:
        ok = False
    else:
        ok = True
    finally:
        if conn is not None:
            conn.close()
        if engine is not None:
            engine.dispose()
    return ok
