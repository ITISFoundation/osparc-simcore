import logging

from fastapi import FastAPI
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiosqlalchemy import (
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import retry

from .logging_utils import log_context
from .retry_policies import PostgresRetryPolicyUponInitialization

_logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
async def connect_to_db(app: FastAPI, settings: PostgresSettings) -> None:
    with log_context(
        _logger, logging.DEBUG, f"connection to db {settings.dsn_with_async_sqlalchemy}"
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

    with log_context(_logger, logging.DEBUG, "migration"):
        try:
            await raise_if_migration_not_ready(engine)
        except Exception:
            # NOTE: engine must be closed because retry will create a new engine
            await engine.dispose()
            raise

    app.state.engine = engine
    _logger.debug(
        "Setup engine: %s",
        await get_pg_engine_stateinfo(engine),
    )


async def close_db_connection(app: FastAPI) -> None:
    with log_context(_logger, logging.DEBUG, f"db disconnect of {app.state.engine}"):
        if engine := app.state.engine:
            await engine.dispose()
