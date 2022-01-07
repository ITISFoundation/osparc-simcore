""" database submodule associated to the postgres service

"""

import logging
from typing import Any, Dict, Optional

from aiohttp import web
from aiopg.sa import Engine
from servicelib.aiohttp.aiopg_utils import is_pg_responsive
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_postgres_database.utils_aiopg import get_pg_engine_stateinfo

from .constants import APP_SETTINGS_KEY
from .db_events import do_connnect_postgress_service

log = logging.getLogger(__name__)


def is_service_enabled(app: web.Application):
    return app.get(APP_DB_ENGINE_KEY) is not None


async def is_service_responsive(app: web.Application):
    """Returns True if the app can connect to db service"""
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

    assert app[APP_SETTINGS_KEY].WEBSERVER_POSTGRES  # nosec

    # async connection to db
    app.cleanup_ctx.append(do_connnect_postgress_service)
