""" users management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)

from . import groups_handlers
from ._constants import APP_OPENAPI_SPECS_KEY
from .scicrunch.submodule_setup import setup_scicrunch_submodule

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest", "simcore_service_webserver.users"],
    logger=logger,
)
def setup_groups(app: web.Application):

    # prepares scicrunch api
    setup_scicrunch_submodule(app)

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = map_handlers_with_operations(
        get_handlers_from_namespace(groups_handlers),
        filter(lambda o: "groups" in o[1].split("/"), iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(routes)
