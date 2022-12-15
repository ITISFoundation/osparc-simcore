""" database submodule associated to the postgres uservice

"""

import logging
from typing import Any, AsyncIterator, Optional

from aiohttp import web
from aiopg.sa import Engine, create_engine
from servicelib.aiohttp.aiopg_utils import is_pg_responsive
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.json_serialization import json_dumps
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from simcore_postgres_database.errors import DBAPIError
from simcore_postgres_database.utils_aiopg import (
    DBMigrationError,
    close_engine,
    get_pg_engine_stateinfo,
    raise_if_migration_not_ready,
)
from tenacity import retry

from .db_settings import PostgresSettings, get_plugin_settings

log = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponInitialization(log).kwargs)
async def _ensure_pg_ready(settings: PostgresSettings) -> Engine:

    log.info("Connecting to postgres with %s", f"{settings=}")
    engine = await create_engine(
        settings.dsn,
        application_name=settings.POSTGRES_CLIENT_NAME,
        minsize=settings.POSTGRES_MINSIZE,
        maxsize=settings.POSTGRES_MAXSIZE,
    )

    try:
        await raise_if_migration_not_ready(engine)
    except (DBMigrationError, DBAPIError):
        await close_engine(engine)
        raise

    log.info("Connection to postgres with %s succeeded", f"{settings=}")
    return engine  # type: ignore # tenacity rules guarantee exit with exc


async def postgres_cleanup_ctx(app: web.Application) -> AsyncIterator[None]:

    settings = get_plugin_settings(app)
    aiopg_engine = await _ensure_pg_ready(settings)
    app[APP_DB_ENGINE_KEY] = aiopg_engine

    log.info("pg engine created %s", json_dumps(get_engine_state(app), indent=1))

    yield  # -------------------

    if aiopg_engine is not app.get(APP_DB_ENGINE_KEY):
        log.critical("app does not hold right db engine. Somebody has changed it??")

    await close_engine(aiopg_engine)

    log.debug(
        "pg engine created after shutdown %s (closed=%s): %s",
        aiopg_engine.dsn,
        aiopg_engine.closed,
        json_dumps(get_engine_state(app), indent=1),
    )


def is_service_enabled(app: web.Application):
    return app.get(APP_DB_ENGINE_KEY) is not None


async def is_service_responsive(app: web.Application):
    """Returns true if the app can connect to db service"""
    if not is_service_enabled(app):
        return False
    is_responsive = await is_pg_responsive(engine=app[APP_DB_ENGINE_KEY])
    return is_responsive


def get_engine_state(app: web.Application) -> dict[str, Any]:
    engine: Optional[Engine] = app.get(APP_DB_ENGINE_KEY)
    if engine:
        return get_pg_engine_stateinfo(engine)
    return {}


def get_database_engine(app: web.Application) -> Engine:
    return app[APP_DB_ENGINE_KEY]


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_DB", logger=log
)
def setup_db(app: web.Application):

    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None

    # async connection to db
    app.cleanup_ctx.append(postgres_cleanup_ctx)
