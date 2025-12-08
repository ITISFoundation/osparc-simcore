"""database submodule associated to the postgres uservice"""

import logging
from typing import Final

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..constants import APP_AIOPG_ENGINE_KEY
from . import _aiopg, _asyncpg

_logger = logging.getLogger(__name__)

DB_ENGINE_APPKEY: Final = web.AppKey(
    "APP_DB_ENGINE_KEY", object
)  # Can be aiopg.Engine or asyncpg engine


# API
get_database_engine_legacy = _aiopg.get_database_engine
get_engine_state = _aiopg.get_engine_state
is_service_responsive = _aiopg.is_service_responsive
is_service_enabled = _aiopg.is_service_enabled


# asyncpg helpers
get_asyncpg_engine = _asyncpg.get_async_engine


@app_setup_func(
    "simcore_service_webserver.db",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DB",
    logger=_logger,
)
def setup_db(app: web.Application):

    # ensures keys exist DEPRECATED
    app[APP_AIOPG_ENGINE_KEY] = None
    assert get_database_engine_legacy(app) is None  # nosec

    # init engines
    app.cleanup_ctx.append(_aiopg.postgres_cleanup_ctx)
    app.cleanup_ctx.append(_asyncpg.postgres_cleanup_ctx)
