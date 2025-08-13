import contextlib
import logging
import time
from collections.abc import AsyncIterator
from datetime import timedelta

from models_library.healthchecks import IsNonResponsive, IsResponsive, LivenessResult
from settings_library.postgres import PostgresSettings
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import retry

from .logging_utils import log_context
from .retry_policies import PostgresRetryPolicyUponInitialization

_logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
async def create_async_engine_and_database_ready(
    settings: PostgresSettings,
) -> AsyncEngine:
    """
    - creates asyncio engine
    - waits until db service is up
    - waits until db data is migrated (i.e. ready to use)
    - returns engine
    """
    from simcore_postgres_database.utils_aiosqlalchemy import (  # type: ignore[import-not-found] # this on is unclear
        raise_if_migration_not_ready,
    )

    server_settings = {"jit": "off"}
    if settings.POSTGRES_CLIENT_NAME:
        assert isinstance(settings.POSTGRES_CLIENT_NAME, str)  # nosec
        server_settings.update(
            {
                "application_name": settings.POSTGRES_CLIENT_NAME,
            }
        )

    engine = create_async_engine(
        settings.dsn_with_async_sqlalchemy,
        pool_size=settings.POSTGRES_MINSIZE,
        max_overflow=settings.POSTGRES_MAXSIZE - settings.POSTGRES_MINSIZE,
        connect_args={"server_settings": server_settings},
        pool_pre_ping=True,  # https://docs.sqlalchemy.org/en/14/core/pooling.html#dealing-with-disconnects
        future=True,  # this uses sqlalchemy 2.0 API, shall be removed when sqlalchemy 2.0 is released
    )

    try:
        await raise_if_migration_not_ready(engine)
    except Exception as exc:
        # NOTE: engine must be closed because retry will create a new engine
        await engine.dispose()
        exc.add_note("Failed during migration check. Created engine disposed.")
        raise

    return engine


async def check_postgres_liveness(engine: AsyncEngine) -> LivenessResult:
    try:
        tic = time.time()
        # test
        async with engine.connect():
            ...
        elapsed_time = time.time() - tic
        return IsResponsive(elapsed=timedelta(seconds=elapsed_time))
    except SQLAlchemyError as err:
        return IsNonResponsive(reason=f"{err}")


@contextlib.asynccontextmanager
async def with_async_pg_engine(
    settings: PostgresSettings,
) -> AsyncIterator[AsyncEngine]:
    """
    Creates an asyncpg engine and ensures it is properly closed after use.
    """
    try:
        with log_context(
            _logger,
            logging.DEBUG,
            f"connection to db {settings.dsn_with_async_sqlalchemy}",
        ):
            server_settings = None
            if settings.POSTGRES_CLIENT_NAME:
                assert isinstance(settings.POSTGRES_CLIENT_NAME, str)

            engine = create_async_engine(
                settings.dsn_with_async_sqlalchemy,
                pool_size=settings.POSTGRES_MINSIZE,
                max_overflow=settings.POSTGRES_MAXSIZE - settings.POSTGRES_MINSIZE,
                connect_args={"server_settings": server_settings},
                pool_pre_ping=True,  # https://docs.sqlalchemy.org/en/14/core/pooling.html#dealing-with-disconnects
                future=True,  # this uses sqlalchemy 2.0 API, shall be removed when sqlalchemy 2.0 is released
            )
        yield engine
    finally:
        with log_context(_logger, logging.DEBUG, f"db disconnect of {engine}"):
            await engine.dispose()
