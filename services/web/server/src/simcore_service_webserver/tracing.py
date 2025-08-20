import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import get_tracing_lifespan
from settings_library.tracing import TracingSettings

from .application_settings import get_application_settings
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
    """
    Sets up OpenTelemetry tracing for the application.

    NOTE: uses app[APP_SETTINGS_KEY].APP_NAME to set the service name advertised to the
    tracing backend. This is used to identify the service in the tracing UI.
    Note that this defaults in _meta.APP_NAME to "simcore-service-webserver" if not set otherwise
    in setup_settings(app, app_name="...") in the application factory.

    """

    app_settings = get_application_settings(app)
    tracing_settings: TracingSettings = get_plugin_settings(app)

    app.cleanup_ctx.append(
        get_tracing_lifespan(
            app=app,
            tracing_settings=tracing_settings,
            service_name=app_settings.APP_NAME,
            add_response_trace_id_header=True,
        )
    )
