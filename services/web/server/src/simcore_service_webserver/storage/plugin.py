""" storage subsystem - manages the interaction with the storage service

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from ..rest.plugin import setup_rest
from . import _rest

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_STORAGE", logger=_logger
)
def setup_storage(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_STORAGE  # nosec

    setup_rest(app)
    app.router.add_routes(_rest.routes)
