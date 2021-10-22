import logging
from io import StringIO
from typing import Any

import orjson
from aiopg.sa import Engine, create_engine
from aiopg.sa.engine import get_dialect
from fastapi import FastAPI
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_migration import get_current_head
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

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
        async with engine.acquire() as conn:
            version_num = await conn.scalar(
                'SELECT "version_num" FROM "alembic_version"'
            )
            head_version_num = get_current_head()
            if version_num != head_version_num:
                raise RuntimeError(
                    f"Migration is incomplete, expected {head_version_num} and got {version_num}"
                )

    except Exception:
        # WARNING: engine must be closed because retry will create a new engine
        engine.close()
        await engine.wait_closed()
        raise
    else:
        logger.debug("Migration up-to-date")

    app.state.engine = engine
    logger.debug(_compose_info_on_engine(app))


async def close_db_connection(app: FastAPI) -> None:
    logger.debug("Disconnecting db ...")

    engine: Engine = app.state.engine
    engine.close()
    await engine.wait_closed()
    logger.debug("Disconnected from %s", engine.dsn)
