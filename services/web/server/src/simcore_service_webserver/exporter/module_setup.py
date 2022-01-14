import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY
from .config import inject_settings
from .request_handlers import rest_handler_functions

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.exporter",
    ModuleCategory.ADDON,
    logger=logger,
)
def setup_exporter(app: web.Application) -> bool:
    # stores settings for this module in the app
    inject_settings(app)

    # Rest-API routes: maps handlers with routes tags with "viewer" based on OAS operation_id
    specs = app[APP_OPENAPI_SPECS_KEY]
    rest_routes = map_handlers_with_operations(
        rest_handler_functions,
        filter(lambda op: "exporter" in op.tags, iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(rest_routes)

    return True
