import logging
from io import StringIO
from typing import Any

import orjson
from aiopg.sa import Engine, create_engine
from aiopg.sa.engine import get_dialect
from fastapi import FastAPI
from models_library.postgres import PostgresSettings
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


ENGINE_ATTRS = "closed driver dsn freesize maxsize minsize name size timeout".split()


pg_retry_policy = dict(
    wait=wait_fixed(5),
    stop=stop_after_attempt(20),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _compose_info_on_engine(app: FastAPI) -> str:
    engine = app.state.engine
    stm = StringIO()
    print("Setup engine:", end=" ", file=stm)
    for attr in ENGINE_ATTRS:
        print(f"{attr}={getattr(engine, attr)}", end="; ", file=stm)
    return stm.getvalue()


def json_serializer(o: Any) -> str:
    return str(orjson.dumps(o), "utf-8")


@retry(**pg_retry_policy)
async def connect_to_db(app: FastAPI, settings: PostgresSettings) -> None:
    logger.debug("Connecting db ...")
    aiopg_dialect = get_dialect(json_serializer=json_serializer)
    engine: Engine = await create_engine(
        str(settings.dsn),
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        minsize=settings.minsize,
        maxsize=settings.maxsize,
        dialect=aiopg_dialect,
    )
    logger.debug("Connected to %s", engine.dsn)
    app.state.engine = engine

    logger.debug(_compose_info_on_engine(app))


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    engine: Engine = app.state.engine
    engine.close()
    await engine.wait_closed()
    logger.debug("Disconnected from %s", engine.dsn)
