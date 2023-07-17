""" Resource tracking service

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _containers_handlers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_RESOURCE_USAGE_TRACKER",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_resource_tracker(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_RESOURCE_USAGE_TRACKER  # nosec
    app.router.add_routes(_containers_handlers.routes)
