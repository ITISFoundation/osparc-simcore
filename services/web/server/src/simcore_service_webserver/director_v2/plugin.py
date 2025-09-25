import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import (
    ModuleCategory,
    app_setup_func,
    is_setup_completed,
)
from ..rest.plugin import setup_rest
from . import _controller
from ._client import DirectorV2RestClient, get_directorv2_client, set_directorv2_client
from ._director_v2_abc_default_service import DefaultProjectRunPolicy
from ._director_v2_abc_service import set_project_run_policy

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIRECTOR_V2",
    logger=_logger,
)
def setup_director_v2(app: web.Application):

    assert app[APP_SETTINGS_APPKEY].WEBSERVER_DIRECTOR_V2  # nosec

    # client to communicate with director-v2 service
    client = DirectorV2RestClient(app)
    set_directorv2_client(app, client)
    assert get_directorv2_client(app) == client  # nosec

    # routes at the web-server app
    setup_rest(app)

    if is_setup_completed(setup_rest.metadata()["module_name"], app):
        set_project_run_policy(app, DefaultProjectRunPolicy())
        app.router.add_routes(_controller.rest.routes)
        app.router.add_routes(_controller.computations_rest.routes)

    else:
        _logger.warning(
            "Skipping computation routes since WEBSERVER_REST plugin is disabled (i.e. service w/o http API)"
        )
