""" database submodule associated to the postgres uservice

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _aiopg, _asyncpg

_logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.db",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DB",
    logger=_logger,
)
def setup_db(app: web.Application):

    # ensures keys exist
    app[APP_DB_ENGINE_KEY] = None

    # async connection to db
    app.cleanup_ctx.append(_aiopg.postgres_cleanup_ctx)
    app.cleanup_ctx.append(_asyncpg.postgres_cleanup_ctx)


# aiopg helpers
get_database_engine = _aiopg.get_database_engine
get_engine_state = _aiopg.get_engine_state
is_service_responsive = _aiopg.is_service_responsive
is_service_enabled = _aiopg.is_service_enabled

# asyncpg helpers
get_async_engine = _asyncpg.get_async_engine
