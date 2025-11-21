import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from . import _handlers
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


@app_setup_func(
    "simcore_service_webserver.activity",
    category=ModuleCategory.ADDON,
    settings_name="WEBSERVER_ACTIVITY",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_activity(app: web.Application):
    assert get_plugin_settings(app)  # nosec

    app.router.add_routes(_handlers.routes)
