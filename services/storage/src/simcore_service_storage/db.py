import logging
from typing import Any, Dict, Optional

from aiohttp import web
from aiopg.sa import Engine
from servicelib.aiohttp.aiopg_utils import (
    DataSourceName,
    init_pg_tables,
    is_pg_responsive,
)
from servicelib.common_aiopg_utils import create_pg_engine
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from tenacity import retry

from .constants import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from .models import metadata
from .settings import PostgresSettings

log = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(log).kwargs)
async def _ensure_pg_ready(dsn: DataSourceName, min_size: int, max_size: int) -> Engine:

    log.info("Creating pg engine for %s", dsn)

    engine = await create_pg_engine(dsn, minsize=min_size, maxsize=max_size)
    try:
        await raise_if_migration_not_ready(engine)
    except Exception:
        await close_engine(engine)
        raise

    return engine  # type: ignore # tenacity rules guarantee exit with exc


async def postgres_cleanup_ctx(app: web.Application):
    engine = None

    pg_cfg: PostgresSettings = app[APP_CONFIG_KEY].STORAGE_POSTGRES
    dsn = DataSourceName(
        application_name=f"{__name__}_{id(app)}",
        database=pg_cfg.POSTGRES_DB,
        user=pg_cfg.POSTGRES_USER,
        password=pg_cfg.POSTGRES_PASSWORD.get_secret_value(),
        host=pg_cfg.POSTGRES_HOST,
        port=pg_cfg.POSTGRES_PORT,
    )  # type: ignore

    log.info("Creating pg engine for %s", dsn)

    engine = await _ensure_pg_ready(
        dsn, min_size=pg_cfg.POSTGRES_MINSIZE, max_size=pg_cfg.POSTGRES_MAXSIZE
    )

    if app[APP_CONFIG_KEY].STORAGE_TESTING:
        log.info("Initializing tables for %s", dsn)
        init_pg_tables(dsn, schema=metadata)

    assert engine  # nosec
    app[APP_DB_ENGINE_KEY] = engine

    yield  # ----------

    if engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    if engine:
        await close_engine(engine)

        log.debug(
            "engine '%s' after shutdown: closed=%s, size=%d",
            engine.dsn,
            engine.closed,
            engine.size,
        )


async def is_service_responsive(app: web.Application):
    """Returns true if the app can connect to db service"""
    is_responsive = await is_pg_responsive(engine=app[APP_DB_ENGINE_KEY])
    return is_responsive


def get_engine_state(app: web.Application) -> Dict[str, Any]:
    engine: Optional[Engine] = app.get(APP_DB_ENGINE_KEY)
    if engine:
        return get_pg_engine_stateinfo(engine)
    return {}


def setup_db(app: web.Application):
    if "postgres" in app[APP_CONFIG_KEY].STORAGE_DISABLE_SERVICES:
        app[APP_DB_ENGINE_KEY] = None
        log.warning("Service '%s' explicitly disabled in config", "postgres")
        return

    app[APP_DB_ENGINE_KEY] = None

    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, "postgres")

    # async connection to db
    app.cleanup_ctx.append(postgres_cleanup_ctx)
