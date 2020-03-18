""" storage subsystem - manages the interaction with the storage service

"""

import logging

from aiohttp import web
from servicelib.application_keys import APP_OPENAPI_SPECS_KEY

from . import storage_routes
from .storage_config import get_config

from servicelib.application_setup import app_module_setup, ModuleCategory

log = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup(app: web.Application):
    specs = app[APP_OPENAPI_SPECS_KEY]  # validated openapi specs

    routes = storage_routes.create(specs)
    app.router.add_routes(routes)


# alias
setup_storage = setup
get_storage_config = get_config


__all__ = ("setup_storage", "get_storage_config")
