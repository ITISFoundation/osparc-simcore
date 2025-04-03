import logging

from aiopg.sa import Engine, create_engine
from fastapi import FastAPI
from servicelib.db_asyncpg_utils import create_async_engine_and_pg_database_ready
from servicelib.logging_utils import log_context
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    get_pg_engine_info,
    raise_if_migration_not_ready,
)
from simcore_postgres_database.utils_aiosqlalchemy import get_pg_engine_stateinfo
from tenacity import retry

from .._meta import PROJECT_NAME

logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(logger).kwargs)
async def connect_to_db(app: FastAPI) -> None:
    logger.debug("Connecting db ...")

    cfg: PostgresSettings = app.state.settings.API_SERVER_POSTGRES
    engine: Engine = await create_engine(
        str(cfg.dsn),
        application_name=cfg.POSTGRES_CLIENT_NAME
        or f"{PROJECT_NAME}_{id(app)}",  # unique identifier per app
        minsize=cfg.POSTGRES_MINSIZE,
        maxsize=cfg.POSTGRES_MAXSIZE,
    )
    logger.debug("Connected to %s", engine.dsn)

    logger.debug("Checking db migrationn ...")
    try:
        await raise_if_migration_not_ready(engine)
    except Exception:
        # NOTE: engine must be closed because retry will create a new engine
        await close_engine(engine)
        raise
    logger.debug("Migration up-to-date")

    app.state.engine = engine
    logger.debug(
        "Setup engine: %s",
        get_pg_engine_info(engine),
    )


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    if engine := app.state.engine:
        await close_engine(engine)

    logger.debug("Disconnected from %s", engine.dsn)


async def asyncpg_connect_to_db(app: FastAPI, settings: PostgresSettings) -> None:
    with log_context(
        logger,
        logging.DEBUG,
        f"Connecting and migraging {settings.dsn_with_async_sqlalchemy}",
    ):
        engine = await create_async_engine_and_pg_database_ready(settings)

    app.state.asyncpg_engine = engine
    logger.debug(
        "Setup engine: %s",
        await get_pg_engine_stateinfo(engine),
    )


async def asyncpg_close_db_connection(app: FastAPI) -> None:
    with log_context(
        logger, logging.DEBUG, f"db disconnect of {app.state.asyncpg_engine}"
    ):
        if engine := app.state.asyncpg_engine:
            await engine.dispose()


def get_asyncpg_engine(app: FastAPI):
    return app.state.asyncpg_engine
