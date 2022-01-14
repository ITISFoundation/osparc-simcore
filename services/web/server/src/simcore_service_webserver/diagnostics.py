import logging
import os
import time
from operator import attrgetter
from typing import Optional

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
from .diagnostics_settings import DiagnosticsSettings

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
    start_sensing_delay: Optional[float] = 60
):
    # NOTE: keep all environs getters inside setup so they can be patched easier for testing
    settings_kwargs = {}

    #
    # Any task blocked more than slow_duration_secs is logged as WARNING
    # Aims to identify possible blocking calls
    #
    if slow_duration_secs is None:
        slow_duration_secs = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 1.0))
    else:
        settings_kwargs["slow_duration_secs"] = slow_duration_secs

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
    else:
        settings_kwargs["max_task_delay"] = max_task_delay

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
    else:
        settings_kwargs["max_avg_response_latency"] = max_avg_response_latency

    app[kMAX_AVG_RESP_LATENCY] = max_avg_response_latency
    log.info("max_avg_response_latency = %3.2f secs ", max_avg_response_latency)

    #
    # Time to start sensinng (secs) for diagnostics since this modules inits
    #
    app[kSTART_SENSING_DELAY_SECS] = start_sensing_delay
    log.info("start_sensing_delay = %3.2f secs ", start_sensing_delay)
    if start_sensing_delay != 60:  # default
        settings_kwargs["start_sensing_delay"] = start_sensing_delay

    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    cfg = DiagnosticsSettings(**settings_kwargs)
    assert cfg.slow_duration_secs == slow_duration_secs  # nosec
    assert cfg.max_task_delay == max_task_delay  # nosec
    assert cfg.max_avg_response_latency == max_avg_response_latency  # nosec
    assert cfg.start_sensing_delay == start_sensing_delay  # nosec
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
