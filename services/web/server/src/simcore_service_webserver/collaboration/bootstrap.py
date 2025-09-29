import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_REALTIME_COLLABORATION",
    logger=_logger,
)
def setup_realtime_collaboration(app: web.Application):
    from .settings import get_plugin_settings

    assert get_plugin_settings(app), "setup_settings not called?"
