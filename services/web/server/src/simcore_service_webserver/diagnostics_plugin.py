import logging
import os
from operator import attrgetter
from typing import Optional

from aiohttp import web

from servicelib import monitor_slow_callbacks

from .diagnostics_core import (
    K_HEALTHCHECK_RETRY,
    K_MAX_AVG_RESP_DELAY,
    K_MAX_CANCEL_RATE,
    K_MAX_DELAY_ALLOWED,
    K_REGISTRY,
    IncidentsRegistry,
)
from .diagnostics_entrypoints import create_routes
from .diagnostics_monitoring import setup_monitoring
from .rest import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__name__)



def setup_diagnostics(
    app: web.Application,
    *,
    slow_duration_secs: Optional[int] = None,
    max_delay_allowed: Optional[int] = None,
    max_cancelations_rate: Optional[int] = None,
    max_avg_response_delay_secs: Optional[int] = 3,
):
    # NOTE: keep environs check inside setup so they can be patched easier for testing
    health_check_interval: float = float(os.environ.get("SC_HEALTHCHECK_INTERVAL", 30))
    health_check_retry: int = int(os.environ.get("SC_HEALTHCHECK_RETRY", 3))

    desc = "min delay to log a callback"
    if slow_duration_secs is None:
        slow_duration_secs = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.2))

    log.info("slow_duration_secs = %3.2f secs (%s)", slow_duration_secs, desc)

    desc = "max delay allowed a callback"
    if max_delay_allowed is None:
        max_delay_allowed = max(
            10 * slow_duration_secs,
            float(os.environ.get("WEBSERVER_DIAGNOSTICS_MAX_DELAY_SECS", 30)),
        )  # secs

    log.info("max_delay_allowed = %3.2f secs (%s)", max_delay_allowed, desc)

    desc = f"max number of task cancelations within {health_check_interval} secs"
    if max_cancelations_rate is None:
        max_cancelations_rate = float(
            os.environ.get("WEBSERVER_DIAGNOSTICS_MAX_DELAY_SECS",)
        )

    max_cancelations_inc = max_cancelations_rate * health_check_interval
    log.info("max_cancelations_per_interval = %3.2f (%s)", max_cancelations_inc, desc)

    # TODO: delay_secs should be automatic
    registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))

    # calls are registered with add(incident)
    monitor_slow_callbacks.enable(max_delay_allowed, registry)

    app[K_REGISTRY] = registry
    app[K_MAX_DELAY_ALLOWED] = max_delay_allowed
    app[K_MAX_CANCEL_RATE] = max_cancelations_rate
    app[K_MAX_AVG_RESP_DELAY] = max_avg_response_delay_secs
    app[K_HEALTHCHECK_RETRY] = health_check_retry
    app[K_HEALTHCHECK_RETRY] = health_check_interval

    create_routes(specs=app[APP_OPENAPI_SPECS_KEY])
    setup_monitoring(app)
