import logging
from typing import Dict, Optional

import attr
import sqlalchemy as sa
from aiopg.sa import create_engine
from aiopg.sa.engine import Engine
from simcore_postgres_database.utils_migration import get_current_head
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

log = logging.getLogger(__name__)


DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"
ENGINE_ATTRS = "closed driver dsn freesize maxsize minsize name size timeout".split()


@attr.s(auto_attribs=True)
class DataSourceName:
    # Attributes for postgres db
    user: str
    password: str = attr.ib(repr=False)
    database: str
    host: str = "127.0.0.1"
    port: int = 5432

    # Attributes about the caller
    application_name: Optional[str] = None

    def asdict(self) -> Dict:
        return attr.asdict(self)

    def to_uri(self, with_query=False) -> str:
        uri = DSN.format(**attr.asdict(self))
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
    awaitable_engine_coro = create_engine(
        dsn.to_uri(),
        application_name=dsn.application_name,
        minsize=minsize,
        maxsize=maxsize,
        **pool_kwargs,
    )
    return awaitable_engine_coro


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


class PostgresRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    WAIT_SECS = 5
    ATTEMPTS_COUNT = 20

    def __init__(self, logger: Optional[logging.Logger] = None):
        logger = logger or log

        self.kwargs = dict(
            wait=wait_fixed(self.WAIT_SECS),
            stop=stop_after_attempt(self.ATTEMPTS_COUNT),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=True,
        )


class DBMigrationError(RuntimeError):
    pass


async def raise_if_migration_not_ready(engine: Engine):
    """Ensures db migration is complete

    :raises DBMigrationError
    :raises
    """
    async with engine.acquire() as conn:
        version_num = await conn.scalar('SELECT "version_num" FROM "alembic_version"')
        head_version_num = get_current_head()
        if version_num != head_version_num:
            raise DBMigrationError(
                f"Migration is incomplete, expected {head_version_num} but got {version_num}"
            )


async def close_engine(engine: Engine) -> None:
    engine.close()
    await engine.wait_closed()
