import logging
from typing import Any

from aiopg.sa.engine import Engine
from fastapi import FastAPI
from servicelib.aiohttp.aiopg_utils import is_pg_responsive
from servicelib.common_aiopg_utils import DataSourceName, create_pg_engine
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from settings_library.postgres import PostgresSettings
from simcore_postgres_database.utils_aiopg import (
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from tenacity import retry

from ...constants import APP_AIOPG_ENGINE_KEY, APP_CONFIG_KEY

_logger = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
async def _ensure_pg_ready(dsn: DataSourceName, min_size: int, max_size: int) -> None:
    _logger.info("Checking pg is ready %s", dsn)

    async with create_pg_engine(dsn, minsize=min_size, maxsize=max_size) as engine:
        await raise_if_migration_not_ready(engine)


async def postgres_cleanup_ctx(app: FastAPI):
    pg_cfg: PostgresSettings = app[APP_CONFIG_KEY].STORAGE_POSTGRES
    dsn = DataSourceName(
        application_name=f"{__name__}_{id(app)}",
        database=pg_cfg.POSTGRES_DB,
        user=pg_cfg.POSTGRES_USER,
        password=pg_cfg.POSTGRES_PASSWORD.get_secret_value(),
        host=pg_cfg.POSTGRES_HOST,
        port=pg_cfg.POSTGRES_PORT,
    )

    await _ensure_pg_ready(
        dsn, min_size=pg_cfg.POSTGRES_MINSIZE, max_size=pg_cfg.POSTGRES_MAXSIZE
    )
    _logger.info("Creating pg engine for %s", dsn)
    async with create_pg_engine(
        dsn, minsize=pg_cfg.POSTGRES_MINSIZE, maxsize=pg_cfg.POSTGRES_MAXSIZE
    ) as engine:
        assert engine  # nosec
        app[APP_AIOPG_ENGINE_KEY] = engine

        _logger.info("Created pg engine for %s", dsn)
        yield  # ----------
        _logger.info("Deleting pg engine for %s", dsn)
    _logger.info("Deleted pg engine for %s", dsn)


async def is_service_responsive(app: FastAPI) -> bool:
    """Returns true if the app can connect to db service"""
    return await is_pg_responsive(engine=app[APP_AIOPG_ENGINE_KEY])


def get_engine_state(app: FastAPI) -> dict[str, Any]:
    engine: Engine | None = app.get(APP_AIOPG_ENGINE_KEY)
    if engine:
        engine_info: dict[str, Any] = get_pg_engine_stateinfo(engine)
        return engine_info
    return {}


def setup_db(app: FastAPI):
    app[APP_AIOPG_ENGINE_KEY] = None

    # app is created at this point but not yet started
    _logger.debug("Setting up %s [service: %s] ...", __name__, "postgres")

    # async connection to db
    app.cleanup_ctx.append(postgres_cleanup_ctx)
