import logging
import time
from operator import attrgetter

from aiohttp import web
from servicelib.aiohttp import monitor_slow_callbacks
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import diagnostics_handlers
from .diagnostics_healthcheck import (
    IncidentsRegistry,
    assert_healthy_app,
    kINCIDENTS_REGISTRY,
    kPLUGIN_START_TIME,
)
from .diagnostics_monitoring import setup_monitoring
from .diagnostics_settings import DiagnosticsSettings, get_plugin_settings
from .rest import HeathCheck

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIAGNOSTICS",
    depends=["simcore_service_webserver.rest"],
    logger=log,
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
    healthcheck: HeathCheck = app[HeathCheck.__name__]
    healthcheck.on_healthcheck.append(assert_healthy_app)

    # adds other diagnostic routes: healthcheck, etc
    app.router.add_routes(diagnostics_handlers.routes)

    app[kPLUGIN_START_TIME] = time.time()
