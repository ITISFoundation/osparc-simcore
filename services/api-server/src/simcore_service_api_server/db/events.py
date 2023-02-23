import logging

from aiopg.sa import Engine, create_engine
from fastapi import FastAPI
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    get_pg_engine_info,
    raise_if_migration_not_ready,
)
from tenacity import retry

from .._meta import PROJECT_NAME
from ..core.settings import PostgresSettings

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
