import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.db_asyncpg_engine import connect_to_postgres_until_ready
from servicelib.logging_utils import log_catch, log_context
from sqlalchemy.ext.asyncio import AsyncEngine

_logger = logging.getLogger(__name__)


postgres_lifespan = LifespanManager()


@postgres_lifespan.add
async def setup_postgres_database(app: FastAPI) -> AsyncIterator[State]:

    with log_context(_logger, logging.INFO, f"{__name__} startup ..."):
        engine: AsyncEngine = await connect_to_postgres_until_ready(
            app.state.settings.CATALOG_POSTGRES
        )

    yield {"engine": engine}

    with log_context(_logger, logging.INFO, f"{__name__} shutdown ..."), log_catch(
        _logger, reraise=False
    ):
        await engine.dispose()
