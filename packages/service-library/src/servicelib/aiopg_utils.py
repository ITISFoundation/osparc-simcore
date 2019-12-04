""" Helpers for aiopg

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
from aiopg.sa import create_engine
from psycopg2 import DatabaseError
from psycopg2 import Error as DBAPIError
from tenacity import (RetryCallState, after_log, before_sleep_log, retry,
                      retry_if_exception_type, stop_after_attempt, wait_fixed)

log = logging.getLogger(__name__)


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
        uri = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        if with_query and self.application_name:
            uri += f"?ApplicationName={self.application_name}"
        return uri



def is_postgres_responsive(dsn: DataSourceName) -> bool:
    """ Returns True if can connect and operate postgres service
    """
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


async def is_postgres_responsive_async(dsn: DataSourceName) -> bool:
    try:
        async with create_engine(dsn.to_uri(), application_name=dsn.application_name) as engine:
            async with engine.acquire() as conn:
                await conn.execute("SELECT 1 as is_alive")
                return True
    except DBAPIError as err:
        log.debug("%s not responsive: %s", dsn, err)
        return False



def raise_http_unavailable_error(retry_state: RetryCallState):
    # aiopg reuses DBAPI exceptions
    #
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
    # SEE https://aiopg.readthedocs.io/en/stable/core.html?highlight=Exception#exceptions
    # SEE http://initd.org/psycopg/docs/module.html#dbapi-exceptions
    # TODO: mark incident on db to determine the quality of service. E.g. next time we do not stop.
    # TODO: add header with Retry-After
    #obj, query = retry_state.args
    #obj.app.register_incidents
    # https://tools.ietf.org/html/rfc7231#section-7.1.3
    raise web.HTTPServiceUnavailable()



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
            after=after_log(logger, logging.ERROR),
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
