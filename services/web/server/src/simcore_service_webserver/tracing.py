import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import setup_tracing

from .application_settings import ApplicationSettings
from .constants import APP_SETTINGS_KEY

log = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, config_section="WEBSERVER_TRACING", logger=log
)
def setup_app_tracing(app: web.Application):

    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    assert settings.WEBSERVER_TRACING  # nosec

    return setup_tracing(
        app,
        service_name="simcore_service_webserver",
        host="0.0.0.0",  # nosec
        port=settings.WEBSERVER_PORT,
        jaeger_base_url=str(settings.WEBSERVER_TRACING.TRACING_ZIPKIN_ENDPOINT),
        # TODO: skip all routes that are ouside vX ??
        skip_routes=None,
    )
