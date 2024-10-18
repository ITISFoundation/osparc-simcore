import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import setup_tracing
from settings_library.tracing import TracingSettings

from ._constants import APP_SETTINGS_KEY
from ._meta import APP_NAME

log = logging.getLogger(__name__)


def get_plugin_settings(app: web.Application) -> TracingSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_TRACING
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, TracingSettings)  # nosec
    return settings


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_TRACING", logger=log
)
def setup_app_tracing(app: web.Application):
    tracing_settings: TracingSettings = get_plugin_settings(app)
    setup_tracing(
        app,
        tracing_settings=tracing_settings,
        service_name=APP_NAME,
    )
