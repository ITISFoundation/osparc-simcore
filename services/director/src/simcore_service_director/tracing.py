import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import setup_tracing

from . import config

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name=None,
    logger=log,  # (settings_name=none for  non-settings-library compatability)
)
def setup_app_tracing(app: web.Application):
    service_name = "simcore_service_director_v0"
    if (
        not config.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT
        or not config.TRACING_OPENTELEMETRY_COLLECTOR_PORT
    ):
        log.warning(
            "Tracing will not be setup. Variables TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT or TRACING_OPENTELEMETRY_COLLECTOR_PORT missing."
        )
    return setup_tracing(
        app,
        service_name=service_name,
        opentelemetry_collector_endpoint=config.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT,
        opentelemetry_collector_port=config.TRACING_OPENTELEMETRY_COLLECTOR_PORT,
    )
