import logging

from aiopg.sa import Engine, create_engine
from aiopg.sa.engine import get_dialect
from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    get_pg_engine_info,
    raise_if_migration_not_ready,
)
from tenacity import retry

logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(logger).kwargs)
async def connect_to_db(app: FastAPI, settings: PostgresSettings) -> None:
    """
    Creates an engine to communicate to the db and retries until
    the db is ready
    """
    logger.debug("Connecting db ...")
    engine: Engine = await create_engine(
        str(settings.dsn),
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        minsize=settings.POSTGRES_MINSIZE,
        maxsize=settings.POSTGRES_MAXSIZE,
        dialect=get_dialect(json_serializer=json_dumps),
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
    logger.debug("Setup engine: %s", get_pg_engine_info(engine))


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    if engine := app.state.engine:
        await close_engine(engine)

    logger.debug("Disconnected from %s", engine.dsn)
