import logging
import os
from operator import attrgetter
from typing import Optional

from aiohttp import web

from servicelib import monitor_slow_callbacks
from servicelib.application_setup import ModuleCategory, app_module_setup

from .diagnostics_core import (
    IncidentsRegistry,
    kINCIDENTS_REGISTRY,
    kMAX_AVG_RESP_LATENCY,
    kMAX_TASK_DELAY,
)
from .diagnostics_entrypoints import create_rest_routes
from .diagnostics_monitoring import setup_monitoring
from .rest import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    config_section="diagnostics",
    logger=log,
)
def setup_diagnostics(
    app: web.Application,
    *,
    slow_duration_secs: Optional[float] = None,
    max_task_delay: Optional[float] = None,
    max_avg_response_latency: Optional[float] = None,
):
    # NOTE: keep all environs getters inside setup so they can be patched easier for testing

    #
    # Any task blocked more than slow_duration_secs is logged as WARNING
    # Aims to identify possible blocking calls
    #
    if slow_duration_secs is None:
        slow_duration_secs = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.3))

    log.info("slow_duration_secs = %3.2f secs ", slow_duration_secs)

    #  TODO: does not have any sense ... Remove!!!
    # Sets an upper threshold for blocking functions, i.e.
    # slow_duration_secs < max_task_delay
    #
    if max_task_delay is None:
        max_task_delay = max(
            10 * slow_duration_secs,
            float(os.environ.get("DIAGNOSTICS_MAX_TASK_DELAY", 0)),
        )  # secs

    app[kMAX_TASK_DELAY] = max_task_delay
    log.info("max_task_delay = %3.2f secs ", max_task_delay)

    #
    # Sets a threshold to the mean latency of the last N request slower
    # than 1 sec is monitored.
    # Aims to control large slowdowns in responses
    #
    if max_avg_response_latency is None:
        max_avg_response_latency = float(
            os.environ.get("DIAGNOSTICS_MAX_AVG_LATENCY", 3)
        )  # secs

    app[kMAX_AVG_RESP_LATENCY] = max_avg_response_latency
    log.info("max_avg_response_latency = %3.2f secs ", max_avg_response_latency)

    #
    # TODO: redesign ... too convoluted!!
    registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))
    app[kINCIDENTS_REGISTRY] = registry

    monitor_slow_callbacks.enable(max_task_delay, registry)

    # adds middleware and /metrics
    setup_monitoring(app)

    # adds other diagnostic routes: healthcheck, etc
    routes = create_rest_routes(specs=app[APP_OPENAPI_SPECS_KEY])
    app.router.add_routes(routes)
