import logging
from io import StringIO

from aiopg.sa import Engine, create_engine
from fastapi import FastAPI
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from ..core.settings import PostgresSettings

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


@retry(**pg_retry_policy)
async def connect_to_db(app: FastAPI) -> None:
    logger.debug("Connecting db ...")

    cfg: PostgresSettings = app.state.settings.postgres
    engine: Engine = await create_engine(
        str(cfg.dsn),
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        minsize=cfg.minsize,
        maxsize=cfg.maxsize,
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
