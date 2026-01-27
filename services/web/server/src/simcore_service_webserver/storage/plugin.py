"""storage subsystem - manages the interaction with the storage service"""

import logging
from typing import Final

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..rest.plugin import setup_rest
from . import _rest

_logger = logging.getLogger(__name__)

APP_STORAGE_CLIENT_KEY: Final = web.AppKey("APP_STORAGE_CLIENT_KEY", object)


@app_setup_func(__name__, ModuleCategory.ADDON, settings_name="WEBSERVER_STORAGE", logger=_logger)
def setup_storage(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_STORAGE  # nosec

    setup_rest(app)
    app.router.add_routes(_rest.routes)
