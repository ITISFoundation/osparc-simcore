import logging
from typing import Any, Dict, Optional

from aiohttp import web
from aiopg.sa import Engine
from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    get_pg_engine_stateinfo,
    init_pg_tables,
    is_pg_responsive,
    raise_if_not_responsive,
)
from tenacity import AsyncRetrying

from .constants import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from .models import metadata
from .settings import PostgresSettings

log = logging.getLogger(__name__)


async def pg_engine(app: web.Application):
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
    async for attempt in AsyncRetrying(
        **PostgresRetryPolicyUponInitialization(log).kwargs
    ):
        with attempt:
            engine = await create_pg_engine(
                dsn, minsize=pg_cfg.POSTGRES_MINSIZE, maxsize=pg_cfg.POSTGRES_MAXSIZE
            )
            await raise_if_not_responsive(engine)

    if app[APP_CONFIG_KEY].STORAGE_TESTING:
        log.info("Initializing tables for %s", dsn)
        init_pg_tables(dsn, schema=metadata)

    assert engine  # nosec
    app[APP_DB_ENGINE_KEY] = engine

    yield  # ----------

    if engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    if engine:
        engine.close()
        await engine.wait_closed()
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
    app.cleanup_ctx.append(pg_engine)
