""" Holderplace for random helpers using aiopg

    - Drop here functions/constants that at that time does
    not fit in any of the setups. Then, they can be moved and
    refactor when new abstractions are used in place.

    - aiopg is used as a client sdk to interact asynchronously with postgres service

    SEE for aiopg: https://aiopg.readthedocs.io/en/stable/sa.html
    SEE for underlying psycopg: http://initd.org/psycopg/docs/module.html
    SEE for extra keywords: https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS
"""
# TODO: Towards implementing https://github.com/ITISFoundation/osparc-simcore/issues/1195

import functools
import logging
from typing import Dict, Optional

import attr
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine, create_engine
from psycopg2 import DatabaseError
from psycopg2 import Error as DBAPIError
from tenacity import (RetryCallState, after_log, before_sleep_log, retry,
                      retry_if_exception_type, stop_after_attempt, wait_fixed)

log = logging.getLogger(__name__)

DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"

@attr.s(auto_attribs=True)
class DataSourceName:
    # Attributes for postgres db
    user: str
    password: str=attr.ib(repr=False)
    database: str
    host: str='localhost'
    port: int=5432

    # Attributes about the caller
    application_name: Optional[str]=None

    def asdict(self) -> Dict:
        return attr.asdict(self)

    def to_uri(self, with_query=False) -> str:
        uri = DSN.format(**attr.asdict(self))
        if with_query and self.application_name:
            uri += f"?application_name={self.application_name}"
        return uri



def create_pg_engine(dsn: DataSourceName, minsize:int=1, maxsize:int=4):
    """ Adapts the arguments of aiopg.sa.create_engine

        Returns a coroutine that is awaitable, i.e.

        async with create_pg_engine as engine:
            assert not engine.closed

        assert engine.closed
    """
    awaitable_engine_coro = create_engine(dsn.to_uri(),
        application_name=dsn.application_name,
        minsize=minsize,
        maxsize=maxsize
    )
    return awaitable_engine_coro


async def raise_if_not_responsive(engine: Engine):
    async with engine.acquire() as conn:
        await conn.execute("SELECT 1 as is_alive")


async def is_pg_responsive(engine: Engine, *, raise_if_fails=False) -> bool:
    try:
        await raise_if_not_responsive(engine)
    except DBAPIError as err:
        log.debug("%s is not responsive: %s", engine.dsn, err)
        if raise_if_fails:
            raise
        return False
    else:
        return True


def init_pg_tables(dsn: DataSourceName, schema: sa.schema.MetaData):
    try:
        # CONS: creates and disposes an engine just to create tables
        # TODO: find a way to create all tables with aiopg engine
        sa_engine = sa.create_engine(dsn.to_uri(with_query=True))
        schema.create_all(sa_engine)
    finally:
        sa_engine.dispose()


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



def raise_http_unavailable_error(retry_state: RetryCallState):
    # TODO: mark incident on db to determine the quality of service. E.g. next time we do not stop. TIP: obj, query = retry_state.args; obj.app.register_incidents

    exc :DatabaseError  = retry_state.outcome.exception()
    # StandardError
    # |__ Warning
    # |__ Error
    #     |__ InterfaceError
    #     |__ DatabaseError
    #         |__ DataError
    #         |__ OperationalError
    #         |__ IntegrityError
    #         |__ InternalError
    #         |__ ProgrammingError
    #         |__ NotSupportedError
    #
    # aiopg reuses DBAPI exceptions
    # SEE https://aiopg.readthedocs.io/en/stable/core.html?highlight=Exception#exceptions
    # SEE http://initd.org/psycopg/docs/module.html#dbapi-exceptions


    # TODO: add header with Retry-After https://tools.ietf.org/html/rfc7231#section-7.1.3
    resp = web.HTTPServiceUnavailable()

    # logs
    msg = f"Postgres service is non-responsive: [{type(exc)}] {str(exc) or repr(exc)}"
    log.error(msg)

    raise resp


class PostgresRetryPolicyUponInitialization:
    """ Retry policy upon service initialization
    """
    WAIT_SECS = 2
    ATTEMPTS_COUNT = 20

    def __init__(self, logger: Optional[logging.Logger]=None):
        logger = logger or log

        self.kwargs = dict(
            wait=wait_fixed(self.WAIT_SECS),
            stop=stop_after_attempt(self.ATTEMPTS_COUNT),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=True
        )

class PostgresRetryPolicyUponOperation:
    """ Retry policy upon service operation
    """
    WAIT_SECS = 2
    ATTEMPTS_COUNT = 3

    def __init__(self, logger: Optional[logging.Logger]=None):
        logger = logger or log

        self.kwargs = dict(
            retry=retry_if_exception_type(DatabaseError),
            wait=wait_fixed(self.WAIT_SECS),
            stop=stop_after_attempt(self.ATTEMPTS_COUNT),
            after=after_log(logger, logging.WARNING),
            retry_error_callback=raise_http_unavailable_error
        )

# alias
postgres_service_retry_policy_kwargs = PostgresRetryPolicyUponOperation().kwargs


def retry_pg_api(func):
    """ Decorator to implement postgres service retry policy and
        keep global  statistics on service attempt fails
    """
    # TODO: temporary. For the time being, use instead postgres_service_retry_policy_kwargs
    _deco_func = retry(**postgres_service_retry_policy_kwargs)(func)
    _total_retry_count = 0

    @functools.wraps(func)
    async def wrapper(*args, **kargs):
        nonlocal _total_retry_count
        try:
            result = await _deco_func(*args, **kargs)
        finally:
            stats = _deco_func.retry.statistics
            _total_retry_count  += int(stats.get('attempt_number', 0))
        return result

    def total_retry_count():
        return _total_retry_count

    wrapper.retry = _deco_func.retry
    wrapper.total_retry_count = total_retry_count
    return wrapper



__all__ = [
    'DBAPIError',
    'PostgresRetryPolicyUponInitialization',
    'PostgresRetryPolicyUponOperation'
]
