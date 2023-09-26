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
# TODO: deprecate this module. Move utils into retry_policies, simcore_postgres_database.utils_aiopg

import functools
import logging

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from psycopg2 import DatabaseError
from psycopg2 import Error as DBAPIError
from tenacity import RetryCallState, retry
from tenacity.after import after_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ..common_aiopg_utils import DataSourceName

log = logging.getLogger(__name__)


async def raise_if_not_responsive(engine: Engine):
    async with engine.acquire() as conn:
        # pylint: disable=protected-access

        # NOTE: Hacks aiopg.sa.SAConnection interface
        #       to override connection's cursor timeout
        cursor = await conn._open_cursor()
        await cursor.execute("SELECT 1 as is_alive", timeout=1)


async def is_pg_responsive(engine: Engine, *, raise_if_fails=False) -> bool:
    try:
        await raise_if_not_responsive(engine)
    except DBAPIError as err:
        log.debug("%s is not responsive: %s", engine.dsn, err)
        if raise_if_fails:
            raise
        return False
    return True


def init_pg_tables(dsn: DataSourceName, schema: sa.schema.MetaData):
    try:
        # CONS: creates and disposes an engine just to create tables
        # TODO: find a way to create all tables with aiopg engine
        sa_engine = sa.create_engine(dsn.to_uri(with_query=True))
        schema.create_all(sa_engine)
    finally:
        sa_engine.dispose()


def raise_http_unavailable_error(retry_state: RetryCallState):
    # TODO: mark incident on db to determine the quality of service. E.g. next time we do not stop. TIP: obj, query = retry_state.args; obj.app.register_incidents

    exc: DatabaseError = retry_state.outcome.exception()
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
    msg = f"Postgres service non-responsive, responding {resp.status_code}: {str(exc) or repr(exc)}"
    log.error(msg)

    raise resp


class PostgresRetryPolicyUponOperation:
    """Retry policy upon service operation"""

    WAIT_SECS = 2
    ATTEMPTS_COUNT = 3

    def __init__(self, logger: logging.Logger | None = None):
        logger = logger or log

        self.kwargs = dict(
            retry=retry_if_exception_type(DatabaseError),
            wait=wait_fixed(self.WAIT_SECS),
            stop=stop_after_attempt(self.ATTEMPTS_COUNT),
            after=after_log(logger, logging.WARNING),
            retry_error_callback=raise_http_unavailable_error,
        )


# alias
postgres_service_retry_policy_kwargs = PostgresRetryPolicyUponOperation().kwargs


def retry_pg_api(func):
    """Decorator to implement postgres service retry policy and
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
            _total_retry_count += int(stats.get("attempt_number", 0))
        return result

    def total_retry_count():
        return _total_retry_count

    wrapper.retry = _deco_func.retry  # type: ignore[attr-defined]
    wrapper.total_retry_count = total_retry_count  # type: ignore[attr-defined]
    return wrapper


__all__ = (
    "DBAPIError",
    "PostgresRetryPolicyUponOperation",
)
