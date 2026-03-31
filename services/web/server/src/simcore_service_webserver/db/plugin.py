"""database submodule associated to the postgres uservice"""

import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from . import _asyncpg

_logger = logging.getLogger(__name__)


# API
get_asyncpg_engine = _asyncpg.get_async_engine


@app_setup_func(
    "simcore_service_webserver.db",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DB",
    logger=_logger,
)
def setup_db(app: web.Application):
    app.cleanup_ctx.append(_asyncpg.postgres_cleanup_ctx)
