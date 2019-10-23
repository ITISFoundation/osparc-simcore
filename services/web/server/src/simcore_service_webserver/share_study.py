""" share study management subsystem


"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import (iter_path_operations,
                                     map_handlers_with_operations)

from . import share_study_handlers
from .rest_config import APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = "share_study"


logger = logging.getLogger(__name__)

def setup(app: web.Application, *, debug=False):
    logger.debug("Setting up %s %s...", __name__, "[debug]" if debug else "")

    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Not section for the moment"

    if not APP_OPENAPI_SPECS_KEY in app:
        log.warning("rest submodule not initialised? share routes will not be defined!")
        return
    specs = app[APP_OPENAPI_SPECS_KEY]

    # routes
    routes = map_handlers_with_operations({
            'get_share_study_links': share_study_handlers.get_share_study_links
        },
        filter(lambda o: "/share" in o[1], iter_path_operations(specs)),
        strict=True
    )
    app.router.add_routes(routes)

# alias
setup_share_study = setup

__all__ = (
    'setup_share_study'
)
