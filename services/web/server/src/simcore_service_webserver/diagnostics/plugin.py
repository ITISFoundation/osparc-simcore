import logging
import time
from operator import attrgetter
from typing import Final

from aiohttp import web
from servicelib.aiohttp import monitor_slow_callbacks
from servicelib.aiohttp.profiler_middleware import profiling_middleware

from ..application_settings import get_application_settings
from ..application_setup import ModuleCategory, app_setup_func
from ..rest.healthcheck import HEALTHCHECK_APPKEY
from ..rest.plugin import setup_rest
from . import _handlers
from ._healthcheck import (
    HEALTH_INCIDENTS_REGISTRY_APPKEY,
    HEALTH_PLUGIN_START_TIME_APPKEY,
    IncidentsRegistry,
    assert_healthy_app,
)
from ._monitoring import setup_monitoring
from .settings import DiagnosticsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

DIAGNOSTICS_CLIENT_APPKEY: Final = web.AppKey("DIAGNOSTICS_CLIENT_APPKEY", object)


async def _on_healthcheck_async_adapter(app: web.Application) -> None:
    assert_healthy_app(app)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIAGNOSTICS",
    logger=_logger,
)
def setup_diagnostics(app: web.Application):
    setup_rest(app)

    settings: DiagnosticsSettings = get_plugin_settings(app)

    incidents_registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))
    app[HEALTH_INCIDENTS_REGISTRY_APPKEY] = incidents_registry

    monitor_slow_callbacks.enable(settings.DIAGNOSTICS_SLOW_DURATION_SECS, incidents_registry)

    # adds middleware and /metrics
    setup_monitoring(app)

    if settings.DIAGNOSTICS_HEALTHCHECK_ENABLED:
        healthcheck = app[HEALTHCHECK_APPKEY]
        healthcheck.on_healthcheck.append(_on_healthcheck_async_adapter)

    # adds other diagnostic routes: healthcheck, etc
    app.router.add_routes(_handlers.routes)

    app[HEALTH_PLUGIN_START_TIME_APPKEY] = time.time()


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PROFILING",
    logger=_logger,
)
def setup_profiling_middleware(app: web.Application):
    assert get_application_settings(app).WEBSERVER_PROFILING  # nosec
    app.middlewares.append(profiling_middleware)
