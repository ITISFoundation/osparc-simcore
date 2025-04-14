import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    app_module_setup,
    is_setup_completed,
)

from ..rest.plugin import setup_rest
from . import _client, _controller
from ._service_abc import set_project_run_policy
from ._service_abc_default import DefaultProjectRunPolicy

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIRECTOR_V2",
    logger=_logger,
)
def setup_director_v2(app: web.Application):

    assert app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR_V2  # nosec

    # client to communicate with director-v2 service
    _client.set_client(app, _client.ComputationsApi(app))

    # routes at the web-server app
    setup_rest(app)

    if is_setup_completed(setup_rest.metadata()["module_name"], app):
        set_project_run_policy(app, DefaultProjectRunPolicy())
        app.router.add_routes(_controller.rest.routes)

    else:
        _logger.warning(
            "Skipping computation routes since WEBSERVER_REST plugin is disabled (i.e. service w/o http API)"
        )
