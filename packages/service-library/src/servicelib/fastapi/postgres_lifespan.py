import asyncio
import logging
from collections.abc import AsyncIterator
from enum import Enum

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.logging_utils import log_catch, log_context
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_database_ready
from .lifespan_utils import LifespanOnStartupError, record_lifespan_called_once

_logger = logging.getLogger(__name__)


class PostgresLifespanState(str, Enum):
    POSTGRES_SETTINGS = "postgres_settings"
    POSTGRES_ASYNC_ENGINE = "postgres.async_engine"


class PostgresConfigurationError(LifespanOnStartupError):
    msg_template = "Invalid postgres settings [={settings}] on startup. Note that postgres cannot be disabled using settings"


def create_postgres_database_input_state(settings: PostgresSettings) -> State:
    return {PostgresLifespanState.POSTGRES_SETTINGS: settings}


async def postgres_database_lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:

    with log_context(_logger, logging.INFO, f"{__name__}"):

        # Mark lifespan as called
        called_state = record_lifespan_called_once(state, "postgres_database_lifespan")

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
