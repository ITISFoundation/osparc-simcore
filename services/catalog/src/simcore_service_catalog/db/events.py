import logging

from fastapi import FastAPI
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiosqlalchemy import (
    close_engine,
    get_pg_engine_info,
    raise_if_migration_not_ready,
)
from tenacity import retry

from ..core.settings import PostgresSettings

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine


@retry(**PostgresRetryPolicyUponInitialization(logger).kwargs)
async def connect_to_db(app: FastAPI) -> None:
    logger.debug("Connecting db ...")
    cfg: PostgresSettings = app.state.settings.CATALOG_POSTGRES
    engine: AsyncEngine = await create_async_engine(
        cfg.dsn,
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        pool_size=cfg.POSTGRES_MINSIZE,
        max_overflow=cfg.POSTGRES_MAXSIZE - cfg.POSTGRES_MINSIZE,
    )
    logger.debug("Connected to %s", engine.url)

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

    logger.debug("Disconnected from %s", engine.url)
