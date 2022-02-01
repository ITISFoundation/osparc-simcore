import logging
import os
import time
from operator import attrgetter

from aiohttp import web
from servicelib.aiohttp import monitor_slow_callbacks
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import diagnostics_handlers
from .diagnostics_core import (
    IncidentsRegistry,
    kINCIDENTS_REGISTRY,
    kMAX_AVG_RESP_LATENCY,
    kMAX_TASK_DELAY,
    kPLUGIN_START_TIME,
    kSTART_SENSING_DELAY_SECS,
)
from .diagnostics_monitoring import setup_monitoring
from .diagnostics_settings import assert_valid_config

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
):
    #
    # Any task blocked more than slow_duration_secs is logged as WARNING
    # Aims to identify possible blocking calls
    #
    slow_duration_secs = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 1.0))
    log.info("slow_duration_secs = %3.2f secs ", slow_duration_secs)

    #  TODO: does not have any sense ... Remove!!!
    # Sets an upper threshold for blocking functions, i.e.
    # slow_duration_secs < max_task_delay
    #
    max_task_delay = max(
        10 * slow_duration_secs,
        float(os.environ.get("DIAGNOSTICS_MAX_TASK_DELAY", 0)),
    )  # secs

    app[kMAX_TASK_DELAY] = max_task_delay
    log.info("DIAGNOSTICS_MAX_TASK_DELAY = %3.2f secs ", max_task_delay)

    #
    # Sets a threshold to the mean latency of the last N request slower
    # than 1 sec is monitored.
    # Aims to control large slowdowns in responses
    #
    max_avg_response_latency = float(
        os.environ.get("DIAGNOSTICS_MAX_AVG_LATENCY", 3)
    )  # secs

    app[kMAX_AVG_RESP_LATENCY] = max_avg_response_latency
    log.info("DIAGNOSTICS_MAX_AVG_LATENCY = %3.2f secs ", max_avg_response_latency)

    #
    # Time to start sensinng (secs) for diagnostics since this modules inits
    #
    start_sensing_delay = float(os.environ.get("DIAGNOSTICS_START_SENSING_DELAY", 60.0))
    app[kSTART_SENSING_DELAY_SECS] = start_sensing_delay
    log.info("start_sensing_delay = %3.2f secs ", start_sensing_delay)

    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(
        slow_duration_secs,
        max_avg_response_latency,
        start_sensing_delay,
        max_task_delay,
    )
    # ---------------------------------------------

    # -----

    # TODO: redesign ... too convoluted!!
    incidents_registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))
    app[kINCIDENTS_REGISTRY] = incidents_registry

    monitor_slow_callbacks.enable(slow_duration_secs, incidents_registry)

    # adds middleware and /metrics
    setup_monitoring(app)

    # adds other diagnostic routes: healthcheck, etc
    app.router.add_routes(diagnostics_handlers.routes)

    app[kPLUGIN_START_TIME] = time.time()
