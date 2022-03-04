import logging

from fastapi import FastAPI
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiosqlalchemy import (
    close_engine,
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import retry

from ..core.settings import PostgresSettings

logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(logger).kwargs)
async def connect_to_db(app: FastAPI) -> None:
    logger.debug("Connecting db ...")
    cfg: PostgresSettings = app.state.settings.CATALOG_POSTGRES
    logger.debug(cfg.dsn)
    modified_dsn = cfg.dsn.replace("postgresql", "postgresql+asyncpg")
    logger.debug(modified_dsn)
    engine: AsyncEngine = create_async_engine(
        modified_dsn,
        pool_size=cfg.POSTGRES_MINSIZE,
        max_overflow=cfg.POSTGRES_MAXSIZE - cfg.POSTGRES_MINSIZE,
        connect_args={
            "server_settings": {"application_name": cfg.POSTGRES_CLIENT_NAME}
        },
    )
    logger.debug("Connected to %s", cfg.dsn)

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
        await get_pg_engine_stateinfo(engine, cfg.POSTGRES_DB),
    )


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    if engine := app.state.engine:
        await close_engine(engine)

    logger.debug("Disconnected from %s", engine.url)
