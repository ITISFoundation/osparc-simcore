import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    app_module_setup,
    is_setup_completed,
)
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from . import director_v2_handlers
from ._constants import APP_OPENAPI_SPECS_KEY
from .director_v2_abc import set_project_run_policy
from .director_v2_core import DefaultProjectRunPolicy, DirectorV2ApiClient, set_client
from .rest import setup_rest

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIRECTOR_V2",
    logger=log,
)
def setup_director_v2(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR_V2  # nosec

    # client to communicate with director-v2 service
    set_client(app, DirectorV2ApiClient(app))

    # routes at the web-server app
    setup_rest(app)

    if is_setup_completed(setup_rest.metadata()["module_name"], app):
        log.debug("Adding routes")

        set_project_run_policy(app, DefaultProjectRunPolicy())

        specs = app[APP_OPENAPI_SPECS_KEY]
        routes = map_handlers_with_operations(
            {
                "get_pipeline": director_v2_handlers.get_pipeline,
                "start_pipeline": director_v2_handlers.start_pipeline,
                "stop_pipeline": director_v2_handlers.stop_pipeline,
            },
            filter(lambda o: "computation" in o[1], iter_path_operations(specs)),
            strict=True,
        )
        # TODO:  app.router.add_routes(director_v2_handlers.routes) and corresponding tests
        app.router.add_routes(routes)

    else:

        log.warning(
            "Skipping computation routes since WEBSERVER_REST plugin is disabled (i.e. service w/o http API)"
        )
