""" A service-independent module with aiopg utils

    This module was necessary because simcore-sdk (an aiohttp-independent package) still needs some
    of the helpers here.
"""
import logging
from dataclasses import asdict, dataclass

import sqlalchemy as sa
from aiopg.sa import create_engine

from .logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)

DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"


@dataclass
class DataSourceName:
    user: str
    password: str
    database: str
    host: str = "127.0.0.1"
    port: int = 5432

    # Attributes about the caller
    application_name: str | None = None

    def to_uri(self, *, with_query=False) -> str:
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
    return create_engine(
        dsn.to_uri(),
        application_name=dsn.application_name,
        minsize=minsize,
        maxsize=maxsize,
        **pool_kwargs,
    )


async def is_postgres_responsive_async(dsn: DataSourceName) -> bool:
    is_responsive: bool = False
    with log_catch(_logger, reraise=False), log_context(
        _logger, logging.DEBUG, msg=f"checking Postgres connection at {dsn=}"
    ):
        async with create_engine(dsn):
            _logger.debug("postgres connection established")
            is_responsive = True

    return is_responsive


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
