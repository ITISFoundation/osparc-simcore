""" users management subsystem


"""

import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import create_routes_from_namespace

from . import users_handlers
from .rest_config import APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = "users"


logger = logging.getLogger(__name__)

def setup(app: web.Application, *, debug=False):
    logger.debug("Setting up %s %s...", __name__, "[debug]" if debug else "")

    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Not section for the moment"
    specs = app[APP_OPENAPI_SPECS_KEY]

    # TODO: Guarantee that *all* /my paths are assigned to users_handlers. One-to-one!
    routes = create_routes_from_namespace(specs, users_handlers)
    app.router.add_routes(routes)

# alias
setup_users = setup

__all__ = (
    'setup_s3'
)
