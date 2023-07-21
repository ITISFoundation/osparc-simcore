import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _handlers
from .settings import get_plugin_settings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.activity",
    category=ModuleCategory.ADDON,
    settings_name="WEBSERVER_ACTIVITY",
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_activity(app: web.Application):
    assert get_plugin_settings(app)  # nosec

    app.router.add_routes(_handlers.routes)
