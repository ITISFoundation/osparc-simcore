""" tags management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _licensed_items_handlers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_LICENSES",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_licenses(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_LICENSES  # nosec

    # routes
    app.router.add_routes(_licensed_items_handlers.routes)
