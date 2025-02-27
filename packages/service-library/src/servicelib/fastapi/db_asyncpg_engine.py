import logging

from fastapi import FastAPI
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiosqlalchemy import (  # type: ignore[import-not-found] # this on is unclear
    get_pg_engine_stateinfo,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db_asyncpg_utils import create_async_engine_and_pg_database_ready
from ..logging_utils import log_context

_logger = logging.getLogger(__name__)


async def connect_to_db(app: FastAPI, settings: PostgresSettings) -> None:
    with log_context(
        _logger,
        logging.DEBUG,
        f"Connecting and migraging {settings.dsn_with_async_sqlalchemy}",
    ):
        engine = await create_async_engine_and_pg_database_ready(settings)

    app.state.engine = engine
    _logger.debug(
        "Setup engine: %s",
        await get_pg_engine_stateinfo(engine),
    )


async def close_db_connection(app: FastAPI) -> None:
    with log_context(_logger, logging.DEBUG, f"db disconnect of {app.state.engine}"):
        if engine := app.state.engine:
            await engine.dispose()


def get_engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)  # nosec
    return app.state.engine
