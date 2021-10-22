import logging
from io import StringIO

from aiopg.sa import Engine, create_engine
from fastapi import FastAPI
from simcore_postgres_database.utils_migration import get_current_head
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

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
    cfg: PostgresSettings = app.state.settings.CATALOG_POSTGRES
    engine: Engine = await create_engine(
        str(cfg.dsn),
        application_name=f"{__name__}_{id(app)}",  # unique identifier per app
        minsize=cfg.POSTGRES_MINSIZE,
        maxsize=cfg.POSTGRES_MAXSIZE,
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

    if engine := app.state.engine:
        engine.close()
        await engine.wait_closed()
    logger.debug("Disconnected from %s", engine.dsn)
