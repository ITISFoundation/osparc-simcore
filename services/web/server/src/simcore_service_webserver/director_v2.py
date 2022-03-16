import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
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

    # dependencies
    setup_rest(app)

    # client
    set_client(app, DirectorV2ApiClient(app))

    # routes
    set_project_run_policy(app, DefaultProjectRunPolicy())

    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = map_handlers_with_operations(
        {
            "start_pipeline": director_v2_handlers.start_pipeline,
            "stop_pipeline": director_v2_handlers.stop_pipeline,
        },
        filter(lambda o: "computation" in o[1], iter_path_operations(specs)),
        strict=True,
    )
    # TODO:  app.router.add_routes(director_v2_handlers.routes) and corresponding tests
    app.router.add_routes(routes)
