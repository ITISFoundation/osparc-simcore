import logging
import os
from operator import attrgetter
from typing import Optional

from aiohttp import web

from servicelib import monitor_slow_callbacks

from .diagnostics_core import (
    IncidentsRegistry,
    kINCIDENTS_REGISTRY,
    kMAX_AVG_RESP_LATENCY,
    kMAX_TASK_DELAY,
)
from .diagnostics_entrypoints import create_routes
from .diagnostics_monitoring import setup_monitoring
from .rest import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__name__)


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
            float(os.environ.get("WEBSERVER_DIAGNOSTICS_MAX_TASK_DELAY", 0)),
        )  # secs

    log.info("max_task_delay = %3.2f secs ", max_task_delay)

    # 
    # Sets a threashold to the mean latency of the last N request slower 
    # than 1 sec is monitored.
    # Aims to control large slowdowns in responses
    #
    if max_avg_response_latency is None:
        max_avg_response_latency = float(
            os.environ.get("WEBSERVER_DIAGNOSTICS_MAX_AVG_RESPONSE_LATENCY", 3)
        )  # secs

    log.info("max_avg_response_latency = %3.2f secs ", max_avg_response_latency)


    # calls are registered with add(incident)
    # TODO: delay_secs should be automatic
    registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))
    monitor_slow_callbacks.enable(max_task_delay, registry)

    # store
    app[kINCIDENTS_REGISTRY] = registry
    app[kMAX_TASK_DELAY] = max_task_delay
    app[kMAX_AVG_RESP_LATENCY] = max_avg_response_latency

    setup_monitoring(app)
    create_routes(specs=app[APP_OPENAPI_SPECS_KEY])
