""" tags management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _groups_handlers, _trash_handlers, _workspaces_handlers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_WORKSPACES",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_workspaces(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_WORKSPACES  # nosec

    # routes
    app.router.add_routes(_workspaces_handlers.routes)
    app.router.add_routes(_groups_handlers.routes)
    app.router.add_routes(_trash_handlers.routes)
