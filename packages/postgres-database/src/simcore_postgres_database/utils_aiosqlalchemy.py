from typing import Any, TypeVar

import sqlalchemy as sa
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


T = TypeVar("T", bound=OsparcErrorMixin)


def map_db_exception(
    exception: Exception,
    exception_map: dict[str, tuple[type[T], dict[str, Any]]],
    default_exception: type[T] | None = None,
) -> T | Exception:
    """Maps SQLAlchemy database exceptions to domain-specific exceptions.

    This function inspects SQLAlchemy and asyncpg exceptions to identify the error type
    by checking pgcodes or error messages, and converts them to appropriate domain exceptions.

    Args:
        exception: The original exception from SQLAlchemy or the database driver
        exception_map: Dictionary mapping pgcode or error string to domain exceptions and params
            Format: {"pgcode_or_error_string": (ExceptionClass, {"param": value})}
        default_exception: Exception class to use if no matching error is found

    Returns:
        Domain-specific exception instance or the original exception if no mapping found
        and no default_exception provided
    """
    pgcode = None
    error_message = str(exception)

    # Handle SQLAlchemy wrapped exceptions
    if isinstance(exception, sa.exc.IntegrityError) and hasattr(exception, "orig"):
        orig_error = exception.orig
        # Handle asyncpg adapter exceptions
        if isinstance(orig_error, AsyncAdapt_asyncpg_dbapi.IntegrityError) and hasattr(
            orig_error, "pgcode"
        ):
            pgcode = orig_error.pgcode
        # Extract any message for substring matching
        if hasattr(orig_error, "pgerror"):
            error_message = str(orig_error.pgerror)

    # Match by pgcode if available
    if pgcode:
        for key, (exc_class, params) in exception_map.items():
            if key == pgcode:
                return exc_class(**params)

    # Match by error message substring
    for key, (exc_class, params) in exception_map.items():
        if key in error_message:
            return exc_class(**params)

    # If no match found, return default exception or original
    if default_exception:
        return default_exception()

    return exception
