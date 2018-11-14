""" director subsystem

    Provides interactivity with the director service
"""

import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from .config import CONFIG_SECTION_NAME
from . import handlers
from servicelib.rest_routing import create_routes_from_namespace
from ..rest_config import APP_OPENAPI_SPECS_KEY

logger = logging.getLogger(__name__)

def setup(app: web.Application):
    logger.debug("Setting up %s ...", __name__)

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["enabled"]:
        logger.warning("'%s' explicitly disabled in config", __name__)
        return


    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = create_routes_from_namespace(specs, handlers)
    app.router.add_routes(routes)


# alias
setup_director = setup

__all__ = (
    'setup_director'
)
