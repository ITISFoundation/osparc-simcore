import logging
from typing import Final

from aiohttp import web
from servicelib.aiohttp.tracing import get_tracing_lifespan
from servicelib.tracing import TracingData
from settings_library.tracing import TracingSettings

from ._meta import APP_NAME
from .application_keys import APP_SETTINGS_APPKEY
from .application_setup import ModuleCategory, app_setup_func

log = logging.getLogger(__name__)

_TRACING_DATA_KEY: Final[str] = "tracing_data"


def get_plugin_settings(app: web.Application) -> TracingSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_TRACING
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, TracingSettings)  # nosec
    return settings


def _setup_tracing_data(app: web.Application, tracing_settings: TracingSettings):
    app[_TRACING_DATA_KEY] = TracingData.create(
        tracing_settings=tracing_settings, service_name=APP_NAME
    )


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
    _setup_tracing_data(app, tracing_settings=tracing_settings)

    app.cleanup_ctx.append(
        get_tracing_lifespan(
            app=app,
            tracing_settings=tracing_settings,
            add_response_trace_id_header=True,
            tracing_data=app[_TRACING_DATA_KEY],
        )
    )
