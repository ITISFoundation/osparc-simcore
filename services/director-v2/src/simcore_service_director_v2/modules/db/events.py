import logging
from io import StringIO
from typing import Any

import orjson
from aiopg.sa import Engine, create_engine
from aiopg.sa.engine import get_dialect
from fastapi import FastAPI
from servicelib.common_aiopg_utils import (
    ENGINE_ATTRS,
    PostgresRetryPolicyUponInitialization,
    close_engine,
    raise_if_migration_not_ready,
)
from settings_library.postgres import PostgresSettings
from tenacity import retry

logger = logging.getLogger(__name__)


def json_serializer(o: Any) -> str:
    return str(orjson.dumps(o), "utf-8")


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
        dialect=get_dialect(json_serializer=json_serializer),
    )
    logger.debug("Connected to %s", engine.dsn)

    logger.debug("Checking db migrationn ...")
    try:
        await raise_if_migration_not_ready(engine)
    except Exception:
        # NOTE: engine must be closed because retry will create a new engine
        await close_engine(engine)
        raise
    else:
        logger.debug("Migration up-to-date")

    app.state.engine = engine
    logger.debug(
        "Setup engine: %s",
        " ".join(f"{attr}={getattr(engine, attr)}" for attr in ENGINE_ATTRS),
    )


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    if engine := app.state.engine:
        await close_engine(engine)

    logger.debug("Disconnected from %s", engine.dsn)
