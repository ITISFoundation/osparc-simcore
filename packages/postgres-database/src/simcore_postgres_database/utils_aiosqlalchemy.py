from typing import Any, TypeAlias, TypeVar

import sqlalchemy as sa
import sqlalchemy.exc as sql_exc
from common_library.errors_classes import OsparcErrorMixin
from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi
from sqlalchemy.ext.asyncio import AsyncEngine

from .utils_migration import get_current_head


async def get_pg_engine_stateinfo(engine: AsyncEngine) -> dict[str, str]:
    checkedin = engine.pool.checkedin()  # type: ignore
    checkedout = engine.pool.checkedout()  # type: ignore
    return {
        "current pool connections": f"{checkedin=},{checkedout=}",
    }


class DBMigrationError(RuntimeError):
    pass


async def raise_if_migration_not_ready(engine: AsyncEngine) -> None:
    """Ensures db migration is complete

    :raises DBMigrationError
    """
    async with engine.connect() as conn:
        version_num = await conn.scalar(
            sa.DDL('SELECT "version_num" FROM "alembic_version"')
        )
        head_version_num = get_current_head()
        if version_num != head_version_num:
            msg = f"Migration is incomplete, expected {head_version_num} but got {version_num}"
            raise DBMigrationError(msg)


AsyncpgSQLState: TypeAlias = str
ErrorT = TypeVar("ErrorT", bound=OsparcErrorMixin)
ErrorKwars: TypeAlias = dict[str, Any]


def map_db_exception(
    exception: Exception,
    exception_map: dict[AsyncpgSQLState, tuple[type[ErrorT], ErrorKwars]],
    default_exception: type[ErrorT] | None = None,
) -> ErrorT | Exception:
    """Maps SQLAlchemy database exceptions to domain-specific exceptions.

    This function inspects SQLAlchemy and asyncpg exceptions to identify the error type
    by checking pgcodes or error messages, and converts them to appropriate domain exceptions.

    Args:
        exception: The original exception from SQLAlchemy or the database driver
        exception_map: Dictionary mapping pgcode
        default_exception: Exception class to use if no matching error is found

    Returns:
        Domain-specific exception instance or the original exception if no mapping found
        and no default_exception provided
    """
    pgcode = None

    # Handle SQLAlchemy wrapped exceptions
    if isinstance(exception, sql_exc.IntegrityError) and hasattr(exception, "orig"):
        orig_error = exception.orig
        # Handle asyncpg adapter exceptions
        if isinstance(orig_error, AsyncAdapt_asyncpg_dbapi.IntegrityError) and hasattr(
            orig_error, "pgcode"
        ):
            assert hasattr(orig_error, "pgcode")  # nosec
            pgcode = orig_error.pgcode

    # Match by pgcode if available
    if pgcode:
        for key, (exc_class, params) in exception_map.items():
            if key == pgcode:
                return exc_class(**params)

    # If no match found, return default exception or original
    return default_exception() if default_exception else exception
