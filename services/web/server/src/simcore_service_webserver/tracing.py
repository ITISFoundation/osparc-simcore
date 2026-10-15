import logging

from aiohttp import web
from servicelib.aiohttp.tracing import TRACING_CONFIG_KEY, setup_tracing

from .application_setup import ModuleCategory, app_setup_func

log = logging.getLogger(__name__)


@app_setup_func(__name__, ModuleCategory.ADDON, settings_name="WEBSERVER_TRACING", logger=log)
def setup_app_tracing(app: web.Application):
    """
    Sets up OpenTelemetry tracing for the application.

    NOTE: uses app[APP_SETTINGS_APPKEY].APP_NAME to set the service name advertised to the
    tracing backend. This is used to identify the service in the tracing UI.
    Note that this defaults in _meta.APP_NAME to "simcore-service-webserver" if not set otherwise
    in setup_settings(app, app_name="...") in the application factory.

    """

    app.cleanup_ctx.append(
        setup_tracing(
            app=app,
            tracing_config=app[TRACING_CONFIG_KEY],
            add_response_trace_id_header=True,
        )
    )
