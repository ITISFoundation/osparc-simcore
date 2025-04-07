import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.logging_utils import log_catch, log_context
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_database_ready

_logger = logging.getLogger(__name__)


postgres_lifespan = LifespanManager()


@postgres_lifespan.add
async def setup_postgres_database(app: FastAPI) -> AsyncIterator[State]:
    with log_context(_logger, logging.INFO, f"{__name__}"):

        pg_settings: PostgresSettings = app.state.settings.CATALOG_POSTGRES

        async_engine: AsyncEngine = await create_async_engine_and_database_ready(
            pg_settings
        )

        yield {"postgres.async_engine": async_engine}

        with log_catch(_logger, reraise=False):
            await async_engine.dispose()
