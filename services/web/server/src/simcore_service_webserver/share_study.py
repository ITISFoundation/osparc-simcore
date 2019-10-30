""" share study management subsystem

"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import create_routes_from_namespace

from . import share_study_handlers
from .rest_config import APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = "share_study"


logger = logging.getLogger(__name__)

def setup(app: web.Application):
    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Not section for the moment"

    if not APP_OPENAPI_SPECS_KEY in app:
        logger.warning("rest submodule not initialised? share routes will not be defined!")
        return False

    specs = app[APP_OPENAPI_SPECS_KEY]

    # routes
    routes = create_routes_from_namespace(specs, share_study_handlers, strict=False)

    app.router.add_routes(routes)

    return True

# alias
setup_share_study = setup

__all__ = (
    'setup_share_study'
)
