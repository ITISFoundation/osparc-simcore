""" tags management subsystem

"""
import logging

from aiohttp import web

from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)

from . import tag_handlers
from .rest_config import APP_OPENAPI_SPECS_KEY

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup(app: web.Application):

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = map_handlers_with_operations(
        get_handlers_from_namespace(tag_handlers),
        filter(lambda o: "tag" in o[3], iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(routes)


# alias
setup_tags = setup

__all__ = "setup_tags"
