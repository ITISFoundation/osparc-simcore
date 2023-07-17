import logging

from fastapi import FastAPI
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiosqlalchemy import (
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import retry

from .retry_policies import PostgresRetryPolicyUponInitialization

logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(logger).kwargs)
async def connect_to_db(app: FastAPI, cfg: PostgresSettings) -> None:
    logger.debug("Connecting db ...")

    engine: AsyncEngine = create_async_engine(
        cfg.dsn_with_async_sqlalchemy,
        pool_size=cfg.POSTGRES_MINSIZE,
        max_overflow=cfg.POSTGRES_MAXSIZE - cfg.POSTGRES_MINSIZE,
        connect_args={
            "server_settings": {"application_name": cfg.POSTGRES_CLIENT_NAME}
        },
        pool_pre_ping=True,  # https://docs.sqlalchemy.org/en/14/core/pooling.html#dealing-with-disconnects
        future=True,  # this uses sqlalchemy 2.0 API, shall be removed when sqlalchemy 2.0 is released
    )

    logger.debug("Connected to %s", engine.url)  # pylint: disable=no-member

    logger.debug("Checking db migration...")
    try:
        await raise_if_migration_not_ready(engine)
    except Exception:
        # NOTE: engine must be closed because retry will create a new engine
        await engine.dispose()
        raise

    logger.debug("Migration up-to-date")

    app.state.engine = engine

    logger.debug(
        "Setup engine: %s",
        await get_pg_engine_stateinfo(engine),
    )


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    if engine := app.state.engine:
        await engine.dispose()

    logger.debug("Disconnected from %s", engine.url)  # pylint: disable=no-member
