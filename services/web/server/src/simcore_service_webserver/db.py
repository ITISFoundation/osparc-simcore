""" database submodule associated to the postgres uservice

"""

import logging

from aiohttp import web
from tenacity import Retrying

from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    is_pg_responsive,
    raise_if_not_responsive,
)
from servicelib.application_keys import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .db_config import CONFIG_SECTION_NAME

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
    for attempt in Retrying(**PostgresRetryPolicyUponInitialization(log).kwargs):
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


def is_service_enabled(app: web.Application):
    return app.get(APP_DB_ENGINE_KEY) is not None


async def is_service_responsive(app: web.Application):
    """ Returns true if the app can connect to db service

    """
    if not is_service_enabled(app):
        return False
    is_responsive = await is_pg_responsive(engine=app[APP_DB_ENGINE_KEY])
    return is_responsive


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None

    # async connection to db
    # app.on_startup.append(_init_db) # TODO: review how is this disposed
    app.cleanup_ctx.append(pg_engine)


# alias ---
setup_db = setup

__all__ = ("setup_db", "is_service_enabled")
