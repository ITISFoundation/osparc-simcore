import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from ..constants import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY
from ..login.decorators import login_required
from .handlers_redirects import get_redirection_to_viewer
from .handlers_rest import rest_handler_functions

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.studies_dispatcher", ModuleCategory.ADDON, logger=logger
)
def setup_studies_dispatcher(app: web.Application) -> bool:
    cfg = app[APP_CONFIG_KEY]["main"]

    # Redirects routes
    redirect_handler = get_redirection_to_viewer
    if not cfg["studies_access_enabled"]:
        redirect_handler = login_required(get_redirection_to_viewer)
        logger.warning(
            "'%s' config explicitly disables anonymous users from this feature",
            __name__,
        )
    app.router.add_routes(
        [web.get("/view", redirect_handler, name="get_redirection_to_viewer")]
    )

    # Rest-API routes: maps handlers with routes tags with "viewer" based on OAS operation_id
    specs = app[APP_OPENAPI_SPECS_KEY]
    rest_routes = map_handlers_with_operations(
        rest_handler_functions,
        filter(lambda op: "viewer" in op.tags, iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(rest_routes)

    return True
