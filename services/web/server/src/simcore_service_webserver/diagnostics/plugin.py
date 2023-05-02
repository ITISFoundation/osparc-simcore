import logging
import time
from operator import attrgetter

from aiohttp import web
from servicelib.aiohttp import monitor_slow_callbacks
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..rest_healthcheck import HealthCheck
from . import _handlers
from ._healthcheck import (
    IncidentsRegistry,
    assert_healthy_app,
    kINCIDENTS_REGISTRY,
    kPLUGIN_START_TIME,
)
from ._monitoring import setup_monitoring
from .settings import DiagnosticsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIAGNOSTICS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_diagnostics(
    app: web.Application,
):
    settings: DiagnosticsSettings = get_plugin_settings(app)

    # TODO: redesign ... too convoluted!!
    incidents_registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))
    app[kINCIDENTS_REGISTRY] = incidents_registry

    monitor_slow_callbacks.enable(
        settings.DIAGNOSTICS_SLOW_DURATION_SECS, incidents_registry
    )

    # adds middleware and /metrics
    setup_monitoring(app)

    # injects healthcheck
    healthcheck: HealthCheck = app[HealthCheck.__name__]

    async def _on_healthcheck_async_adapter(app: web.Application):
        assert_healthy_app(app)

    healthcheck.on_healthcheck.append(_on_healthcheck_async_adapter)  # type: ignore

    # adds other diagnostic routes: healthcheck, etc
    app.router.add_routes(_handlers.routes)

    app[kPLUGIN_START_TIME] = time.time()
