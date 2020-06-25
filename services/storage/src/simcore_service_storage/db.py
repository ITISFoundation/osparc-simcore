import logging

from aiohttp import web
from tenacity import Retrying

from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    init_pg_tables,
    is_pg_responsive,
    raise_if_not_responsive,
)

from .models import metadata
from .settings import APP_CONFIG_KEY, APP_DB_ENGINE_KEY

log = logging.getLogger(__name__)

THIS_SERVICE_NAME = "postgres"


async def pg_engine(app: web.Application):
    pg_cfg = app[APP_CONFIG_KEY][THIS_SERVICE_NAME]
    dsn = DataSourceName(
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

    if app[APP_CONFIG_KEY]["main"]["testing"]:
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
    """ Returns true if the app can connect to db service

    """
    is_responsive = await is_pg_responsive(engine=app[APP_DB_ENGINE_KEY])
    return is_responsive


def setup_db(app: web.Application):
    disable_services = app[APP_CONFIG_KEY].get("main", {}).get("disable_services", [])

    if THIS_SERVICE_NAME in disable_services:
        app[APP_DB_ENGINE_KEY] = None
        log.warning("Service '%s' explicitly disabled in config", THIS_SERVICE_NAME)
        return

    app[APP_DB_ENGINE_KEY] = None

    # app is created at this point but not yet started
    log.debug("Setting up %s [service: %s] ...", __name__, THIS_SERVICE_NAME)

    # async connection to db
    app.cleanup_ctx.append(pg_engine)
