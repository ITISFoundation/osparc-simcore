import asyncio
import logging
from collections.abc import AsyncIterator
from enum import Enum

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_database_ready
from ..logging_utils import log_catch
from .lifespan_utils import LifespanOnStartupError, lifespan_context

_logger = logging.getLogger(__name__)


class PostgresLifespanState(str, Enum):
    POSTGRES_SETTINGS = "postgres_settings"
    POSTGRES_ASYNC_ENGINE = "postgres.async_engine"


class PostgresConfigurationError(LifespanOnStartupError):
    msg_template = "Invalid postgres settings [={settings}] on startup. Note that postgres cannot be disabled using settings"


def create_postgres_database_input_state(settings: PostgresSettings) -> State:
    return {PostgresLifespanState.POSTGRES_SETTINGS: settings}


async def postgres_database_lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:

    _lifespan_name = f"{__name__}.{postgres_database_lifespan.__name__}"

    with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
        # Validate input state
        settings = state[PostgresLifespanState.POSTGRES_SETTINGS]

        if settings is None or not isinstance(settings, PostgresSettings):
            raise PostgresConfigurationError(settings=settings)

        assert isinstance(settings, PostgresSettings)  # nosec

        # connect to database
        async_engine: AsyncEngine = await create_async_engine_and_database_ready(
            settings
        )

        try:

            yield {
                PostgresLifespanState.POSTGRES_ASYNC_ENGINE: async_engine,
                **called_state,
            }

        finally:
            with log_catch(_logger, reraise=False):
                await asyncio.wait_for(async_engine.dispose(), timeout=10)
