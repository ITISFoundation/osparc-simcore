""" users management subsystem


"""

import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations, get_handlers_from_namespace

from . import users_handlers
from .rest_config import APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = "users"


logger = logging.getLogger(__name__)

def setup(app: web.Application, *, debug=False):
    logger.debug("Setting up %s %s...", __name__, "[debug]" if debug else "")

    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Not section for the moment"

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    routes = map_handlers_with_operations(
            get_handlers_from_namespace(users_handlers),
            filter(lambda o: "/my" in o[1],  iter_path_operations(specs)),
            strict=True
    )
    app.router.add_routes(routes)


# alias
setup_users = setup

__all__ = (
    'setup_users'
)
