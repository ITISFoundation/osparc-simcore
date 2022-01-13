""" storage subsystem - manages the interaction with the storage service

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import storage_routes
from .storage_settings import assert_valid_config

log = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup_storage(app: web.Application):
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(app)
    # ---------------------------------------------

    specs = app[APP_OPENAPI_SPECS_KEY]  # validated openapi specs

    routes = storage_routes.create(specs)
    app.router.add_routes(routes)
