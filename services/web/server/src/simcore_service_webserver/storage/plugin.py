""" storage subsystem - manages the interaction with the storage service

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _routes

log = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_STORAGE", logger=log
)
def setup_storage(app: web.Application):

    specs = app[APP_OPENAPI_SPECS_KEY]  # validated openapi specs

    routes = _routes.create(specs)
    app.router.add_routes(routes)
