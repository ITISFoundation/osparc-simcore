""" database submodule associated to the postgres uservice

"""

import logging
from typing import Any, AsyncIterator, Dict, Optional

from aiohttp import web
from aiopg.sa import Engine
from servicelib.aiohttp.aiopg_utils import DataSourceName, is_pg_responsive
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.common_aiopg_utils import create_pg_engine
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from tenacity import retry

from .db_config import CONFIG_SECTION_NAME
from .db_settings import assert_valid_config

THIS_MODULE_NAME = __name__.split(".")[-1]
THIS_SERVICE_NAME = "postgres"

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


async def postgres_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    pg_cfg = cfg["postgres"]

    dsn = DataSourceName(
        application_name=f"{__name__}_{id(app)}",
        database=pg_cfg["database"],
        user=pg_cfg["user"],
        password=pg_cfg["password"],
        host=pg_cfg["host"],
        port=pg_cfg["port"],
    )  # type: ignore
    aiopg_engine = await _ensure_pg_ready(dsn, pg_cfg["minsize"], pg_cfg["maxsize"])
    app[APP_DB_ENGINE_KEY] = aiopg_engine

    yield  # -------------------

    # clean-up
    if aiopg_engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    for engine in [aiopg_engine]:
        await close_engine(engine)

        log.debug(
            "engine '%s' after shutdown: closed=%s, size=%d",
            engine.dsn,
            engine.closed,
            engine.size,
        )


def is_service_enabled(app: web.Application):
    return app.get(APP_DB_ENGINE_KEY) is not None


async def is_service_responsive(app: web.Application):
    """Returns true if the app can connect to db service"""
    if not is_service_enabled(app):
        return False
    is_responsive = await is_pg_responsive(engine=app[APP_DB_ENGINE_KEY])
    return is_responsive


def get_engine_state(app: web.Application) -> Dict[str, Any]:
    engine: Optional[Engine] = app.get(APP_DB_ENGINE_KEY)
    if engine:
        return get_pg_engine_stateinfo(engine)
    return {}


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup_db(app: web.Application):
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(app)
    # ---------------------------------------------

    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None

    # async connection to db
    app.cleanup_ctx.append(postgres_cleanup_ctx)
