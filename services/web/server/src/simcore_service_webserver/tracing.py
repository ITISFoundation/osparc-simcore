import logging

from aiohttp import web
from servicelib.aiohttp.tracing import TRACING_DATA_KEY, setup_tracing
from servicelib.tracing import TracingData
from settings_library.tracing import TracingSettings

from .application_keys import APP_SETTINGS_APPKEY
from .application_setup import ModuleCategory, app_setup_func

log = logging.getLogger(__name__)


def get_plugin_settings(app: web.Application) -> TracingSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_TRACING
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, TracingSettings)  # nosec
    return settings


@app_setup_func(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_TRACING", logger=log
)
def setup_app_tracing(app: web.Application):
    """
    Sets up OpenTelemetry tracing for the application.

    NOTE: uses app[APP_SETTINGS_APPKEY].APP_NAME to set the service name advertised to the
    tracing backend. This is used to identify the service in the tracing UI.
    Note that this defaults in _meta.APP_NAME to "simcore-service-webserver" if not set otherwise
    in setup_settings(app, app_name="...") in the application factory.

    """

    tracing_settings: TracingSettings = get_plugin_settings(app)
    tracing_data = TracingData.create(
        tracing_settings=tracing_settings,
        service_name=app[APP_SETTINGS_APPKEY].APP_NAME,
    )
    app[TRACING_DATA_KEY] = tracing_data

    app.cleanup_ctx.append(
        setup_tracing(
            app=app,
            tracing_data=tracing_data,
            add_response_trace_id_header=True,
        )
    )
