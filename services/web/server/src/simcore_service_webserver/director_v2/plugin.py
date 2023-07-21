import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    app_module_setup,
    is_setup_completed,
)

from ..rest.plugin import setup_rest
from . import _handlers as director_v2_handlers
from ._abc import set_project_run_policy
from ._core_computations import ComputationsApi, set_client
from ._core_utils import DefaultProjectRunPolicy

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
    set_client(app, ComputationsApi(app))

    # routes at the web-server app
    setup_rest(app)

    if is_setup_completed(setup_rest.metadata()["module_name"], app):
        set_project_run_policy(app, DefaultProjectRunPolicy())
        app.router.add_routes(director_v2_handlers.routes)

    else:
        log.warning(
            "Skipping computation routes since WEBSERVER_REST plugin is disabled (i.e. service w/o http API)"
        )
