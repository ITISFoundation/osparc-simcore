import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY
from .request_handlers import rest_handler_functions
from .settings import get_settings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.exporter",
    ModuleCategory.ADDON,
    logger=logger,
)
def setup_exporter(app: web.Application) -> bool:

    # TODO: Implements temporary plugin disabling mechanims until new settings are fully integrated in servicelib.aiohttp.app_module_setup
    try:
        if get_settings(app) is None:
            raise SkipModuleSetup(
                reason="{__name__} plugin was explictly disabled in the app settings"
            )
    except KeyError as err:
        # This will happen if app[APP_SETTINGS_KEY] raises
        raise SkipModuleSetup(reason="{__name__} plugin settings undefined") from err

    # Rest-API routes: maps handlers with routes tags with "viewer" based on OAS operation_id
    specs = app[APP_OPENAPI_SPECS_KEY]
    rest_routes = map_handlers_with_operations(
        rest_handler_functions,
        filter(lambda op: "exporter" in op.tags, iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(rest_routes)

    return True
