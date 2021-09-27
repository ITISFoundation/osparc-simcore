import logging
from typing import Tuple

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from . import director_v2_handlers
from .director_v2_core import (
    create_or_update_pipeline,
    delete_pipeline,
    get_computation_task,
    get_service_state,
    get_services,
    is_healthy,
    request_retrieve_dyn_service,
    start_service,
    stop_service,
    stop_services,
)
from .director_v2_settings import CONFIG_SECTION_NAME, create_settings
from .rest_config import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__file__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    config_section=CONFIG_SECTION_NAME,
    depends=["simcore_service_webserver.rest"],
    logger=log,
)
def setup_director_v2(app: web.Application):
    # create settings and injects in app
    create_settings(app)

    if not APP_OPENAPI_SPECS_KEY in app:
        log.warning(
            "rest submodule not initialised? computation routes will not be defined!"
        )
        return

    specs = app[APP_OPENAPI_SPECS_KEY]
    # bind routes with handlers
    routes = map_handlers_with_operations(
        {
            "start_pipeline": director_v2_handlers.start_pipeline,
            "stop_pipeline": director_v2_handlers.stop_pipeline,
        },
        filter(lambda o: "computation" in o[1], iter_path_operations(specs)),
        strict=True,
    )
    # FIXME:  app.router.add_routes(director_v2_handlers.routes)
    app.router.add_routes(routes)


# API
__all__: Tuple[str, ...] = (
    "create_or_update_pipeline",
    "delete_pipeline",
    "get_computation_task",
    "get_service_state",
    "get_services",
    "is_healthy",
    "request_retrieve_dyn_service",
    "start_service",
    "stop_service",
    "stop_services",
)
