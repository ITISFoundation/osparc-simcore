import logging
import time
from datetime import timedelta

from models_library.healthchecks import IsNonResponsive, IsResponsive, LivenessResult
from servicelib.logging_utils import log_context
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiosqlalchemy import (  # type: ignore[import-not-found] # this on is unclear
    raise_if_migration_not_ready,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import retry

from .logging_utils import log_context
from .retry_policies import PostgresRetryPolicyUponInitialization

_logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
async def create_async_engine_and_pg_database_ready(
    settings: PostgresSettings,
) -> AsyncEngine:
    """
    - creates asynio engine
    - waits until db service is up
    - waits until db data is migrated (i.e. ready to use)
    - returns engine
    """
    with log_context(
        _logger, logging.DEBUG, f"Connecting to {settings.dsn_with_async_sqlalchemy}"
    ):
        engine: AsyncEngine = create_async_engine(
            settings.dsn_with_async_sqlalchemy,
            pool_size=settings.POSTGRES_MINSIZE,
            max_overflow=settings.POSTGRES_MAXSIZE - settings.POSTGRES_MINSIZE,
            connect_args={
                "server_settings": {"application_name": settings.POSTGRES_CLIENT_NAME}
            },
            pool_pre_ping=True,  # https://docs.sqlalchemy.org/en/14/core/pooling.html#dealing-with-disconnects
            future=True,  # this uses sqlalchemy 2.0 API, shall be removed when sqlalchemy 2.0 is released
        )

    with log_context(
        _logger, logging.DEBUG, f"Migrating db {settings.dsn_with_async_sqlalchemy}"
    ):
        try:
            await raise_if_migration_not_ready(engine)
        except Exception:
            # NOTE: engine must be closed because retry will create a new engine
            await engine.dispose()
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
