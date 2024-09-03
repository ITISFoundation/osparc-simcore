import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import setup_tracing
from settings_library.tracing import TracingSettings

from ._constants import APP_SETTINGS_KEY

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
    settings: TracingSettings = get_plugin_settings(app)
    setup_tracing(
        app,
        opentelemetry_collector_endpoint=settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT,
        opentelemetry_collector_port=settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT,
        instrument_aiopg=True,
        service_name=app.state.settings.APP_NAME,
    )
