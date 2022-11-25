""" tags management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import tags_handlers

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_TAGS",
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_tags(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_TAGS  # nosec
    app.router.add_routes(tags_handlers.routes)
