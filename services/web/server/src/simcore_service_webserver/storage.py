''' Subsystem that communicates with the storage service '''

import logging

from aiohttp import web

from . import storage_routes
from .application_keys import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__name__)

def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    specs = app[APP_OPENAPI_SPECS_KEY] # validated openapi specs

    routes = storage_routes.create(specs)
    app.router.add_routes(routes)

# alias
setup_storage = setup

__all__ = (
    'setup_storage'
)
