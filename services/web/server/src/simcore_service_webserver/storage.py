''' Subsystem that communicates with the storage service '''

import logging

from aiohttp import web

from . import storage_routes
from .application_keys import APP_OPENAPI_SPECS_KEY
from .storage_settings import get_config

# SETTINGS ----------------------------------------------------
THIS_MODULE_NAME = __name__.split(".")[-1]

# --------------------------------------------------------------

log = logging.getLogger(__name__)

def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    specs = app[APP_OPENAPI_SPECS_KEY] # validated openapi specs

    routes = storage_routes.create(specs)
    app.router.add_routes(routes)

# alias
setup_storage = setup
get_storage_config = get_config


__all__ = (
    'setup_storage',
    'get_storage_config'
)
