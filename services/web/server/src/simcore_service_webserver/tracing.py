import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import get_tracing_lifespan
from settings_library.tracing import TracingSettings

from ._meta import APP_NAME
from .constants import APP_SETTINGS_KEY

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
    app.cleanup_ctx.append(
        get_tracing_lifespan(
            app,
            tracing_settings=tracing_settings,
            service_name=APP_NAME,
            add_response_trace_id_header=True,
        )
    )
