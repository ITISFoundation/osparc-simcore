import logging

from fastapi import FastAPI
from servicelib.db_asyncpg_utils import create_async_engine_and_pg_database_ready
from servicelib.logging_utils import log_context
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiosqlalchemy import get_pg_engine_stateinfo

_logger = logging.getLogger(__name__)


async def asyncpg_connect_to_db(app: FastAPI, settings: PostgresSettings) -> None:
    with log_context(
        _logger,
        logging.DEBUG,
        f"Connecting and migraging {settings.dsn_with_async_sqlalchemy}",
    ):
        engine = await create_async_engine_and_pg_database_ready(settings)

    app.state.asyncpg_engine = engine
    _logger.debug(
        "Setup engine: %s",
        await get_pg_engine_stateinfo(engine),
    )


async def asyncpg_close_db_connection(app: FastAPI) -> None:
    with log_context(
        _logger, logging.DEBUG, f"db disconnect of {app.state.asyncpg_engine}"
    ):
        if engine := app.state.asyncpg_engine:
            await engine.dispose()


def get_asyncpg_engine(app: FastAPI):
    return app.state.asyncpg_engine
