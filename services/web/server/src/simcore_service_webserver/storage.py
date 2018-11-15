""" storage subsystem - manages the interaction with the storage service

"""

import logging

from aiohttp import ClientSession, web

from servicelib.application_keys import APP_OPENAPI_SPECS_KEY

from . import storage_routes
from .storage_config import APP_STORAGE_SESSION_KEY, get_config


log = logging.getLogger(__name__)

async def storage_client_ctx(app: web.Application):
    # TODO: deduce base url from configuration and add to session
    async with ClientSession(loop=app.loop) as session: # TODO: check if should keep webserver->storage session?
        app[APP_STORAGE_SESSION_KEY] = session
        yield

    log.debug("cleanup session")



def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    specs = app[APP_OPENAPI_SPECS_KEY] # validated openapi specs

    routes = storage_routes.create(specs)
    app.router.add_routes(routes)

    app.cleanup_ctx.append(storage_client_ctx)

# alias
setup_storage = setup
get_storage_config = get_config


__all__ = (
    'setup_storage',
    'get_storage_config'
)
