import logging
from collections.abc import AsyncIterator
from enum import Enum

from fastapi_lifespan_manager import LifespanManager, State
from servicelib.logging_utils import log_catch, log_context
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_database_ready
from .lifespan_utils import LifespanOnStartupError

_logger = logging.getLogger(__name__)


postgres_lifespan_manager = LifespanManager()


class PostgresLifespanStateKeys(str, Enum):
    POSTGRES_SETTINGS = "postgres_settings"
    POSTGRES_ASYNC_ENGINE = "postgres.async_engine"


class PostgresConfigurationError(LifespanOnStartupError):
    msg_template = "Invalid postgres settings [={pg_settings}] on startup. Note that postgres cannot be disabled using settings"


@postgres_lifespan_manager.add
async def setup_postgres_database(_, state: State) -> AsyncIterator[State]:

    with log_context(_logger, logging.INFO, f"{__name__}"):

        pg_settings: PostgresSettings | None = state[
            PostgresLifespanStateKeys.POSTGRES_SETTINGS
        ]

        if pg_settings is None or not isinstance(pg_settings, PostgresSettings):
            raise PostgresConfigurationError(pg_settings=pg_settings, module="postgres")

        assert isinstance(pg_settings, PostgresSettings)  # nosec

        async_engine: AsyncEngine = await create_async_engine_and_database_ready(
            pg_settings
        )

        try:
            yield {
                PostgresLifespanStateKeys.POSTGRES_ASYNC_ENGINE: async_engine,
            }

        finally:
            with log_catch(_logger, reraise=False):
                await async_engine.dispose()
