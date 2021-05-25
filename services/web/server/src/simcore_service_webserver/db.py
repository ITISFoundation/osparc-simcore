""" database submodule associated to the postgres uservice

"""

import logging
from typing import Any, Dict, Optional

from aiohttp import web
from aiopg.sa import Engine
from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    get_pg_engine_stateinfo,
    is_pg_responsive,
    raise_if_not_responsive,
)
from servicelib.application_keys import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from tenacity import AsyncRetrying

from .db_config import CONFIG_SECTION_NAME, assert_valid_config

THIS_MODULE_NAME = __name__.split(".")[-1]
THIS_SERVICE_NAME = "postgres"

log = logging.getLogger(__name__)


async def pg_engine(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    pg_cfg = cfg["postgres"]

    app[f"{__name__}.dsn"] = dsn = DataSourceName(
        application_name=f"{__name__}_{id(app)}",
        database=pg_cfg["database"],
        user=pg_cfg["user"],
        password=pg_cfg["password"],
        host=pg_cfg["host"],
        port=pg_cfg["port"],
    )

    log.info("Creating pg engine for %s", dsn)
    async for attempt in AsyncRetrying(
        **PostgresRetryPolicyUponInitialization(log).kwargs
    ):
        with attempt:
            engine = await create_pg_engine(
                dsn, minsize=pg_cfg["minsize"], maxsize=pg_cfg["maxsize"]
            )
            await raise_if_not_responsive(engine)

    assert engine  # nosec
    app[APP_DB_ENGINE_KEY] = engine

    yield  # -------------------

    if engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    engine.close()
    await engine.wait_closed()
    log.debug(
        "engine '%s' after shutdown: closed=%s, size=%d",
        engine.dsn,
        engine.closed,
        engine.size,
    )


async def _create_pg_engine(
    dsn: DataSourceName, min_size: int, max_size: int
) -> Engine:
    log.info("Creating pg engine for %s", dsn)
    async for attempt in AsyncRetrying(
        **PostgresRetryPolicyUponInitialization(log).kwargs
    ):
        with attempt:
            engine = await create_pg_engine(dsn, minsize=min_size, maxsize=max_size)
            await raise_if_not_responsive(engine)

    assert engine  # nosec
    return engine


async def pg_engines(app: web.Application) -> None:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    pg_cfg = cfg["postgres"]

    dsn = DataSourceName(
        application_name=f"{__name__}_{id(app)}",
        database=pg_cfg["database"],
        user=pg_cfg["user"],
        password=pg_cfg["password"],
        host=pg_cfg["host"],
        port=pg_cfg["port"],
    )
    normal_engine = await _create_pg_engine(dsn, pg_cfg["minsize"], pg_cfg["maxsize"])
    app[APP_DB_ENGINE_KEY] = normal_engine

    yield  # -------------------

    # clean-up
    if normal_engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    for engine in [normal_engine]:
        engine.close()
        await engine.wait_closed()
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
def setup(app: web.Application):
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(app)
    # ---------------------------------------------

    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None

    # async connection to db
    # app.on_startup.append(_init_db) # TODO: review how is this disposed
    app.cleanup_ctx.append(pg_engines)


# alias ---
setup_db = setup

__all__ = ("setup_db", "is_service_enabled")
