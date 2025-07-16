import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_REALTIME_COLLABORATION",
    logger=_logger,
)
def setup_realtime_collaboration(app: web.Application):
    from .settings import get_plugin_settings

    assert get_plugin_settings(app), "setup_settings not called?"
