import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional

from aiohttp import web
from servicelib.aiohttp.incidents import LimitedOrderedStack, SlowCallback

from .diagnostics_settings import get_plugin_settings
from .rest_healthcheck import HealthCheckFailed

log = logging.getLogger(__name__)

# APP KEYS ---
kINCIDENTS_REGISTRY = f"{__name__}.incidents_registry"
kLAST_REQUESTS_AVG_LATENCY = f"{__name__}.last_requests_avg_latency"
kMAX_AVG_RESP_LATENCY = f"{__name__}.max_avg_response_latency"
kMAX_TASK_DELAY = f"{__name__}.max_task_delay"

kLATENCY_PROBE = f"{__name__}.latency_probe"
kPLUGIN_START_TIME = f"{__name__}.plugin_start_time"

kSTART_SENSING_DELAY_SECS = f"{__name__}.start_sensing_delay"


class IncidentsRegistry(LimitedOrderedStack[SlowCallback]):
    def max_delay(self) -> float:
        return self.max_item.delay_secs if self else 0


@dataclass
class DelayWindowProbe:
    """
    Collects a window of delay samples that satisfy
    some conditions (see observe code)
    """

    min_threshold_secs: float = 0.3
    max_window: int = 100
    last_delays: List = field(default_factory=list)

    def observe(self, delay: float):
        # Mean latency of the last N request slower than min_threshold_secs sec
        if delay > self.min_threshold_secs:
            fifo = self.last_delays
            fifo.append(delay)
            if len(fifo) > self.max_window:
                fifo.pop(0)

    def value(self) -> float:
        if self.last_delays:
            return statistics.mean(self.last_delays)
        return 0


logged_once = False


def is_sensing_enabled(app: web.Application):
    """Diagnostics will not activate sensing inmediatly but after some
    time since the app started
    """
    global logged_once  # pylint: disable=global-statement
    settings = get_plugin_settings(app)

    time_elapsed_since_setup = time.time() - app[kPLUGIN_START_TIME]
    enabled = time_elapsed_since_setup > settings.DIAGNOSTICS_START_SENSING_DELAY
    if enabled and not logged_once:
        log.debug(
            "Diagnostics starts sensing after waiting %3.2f secs [> %3.2f secs] since submodule init",
            time_elapsed_since_setup,
            settings.DIAGNOSTICS_START_SENSING_DELAY,
        )
        logged_once = True
    return enabled


def assert_healthy_app(app: web.Application) -> None:
    """Diagnostics function that determins whether
    current application is healthy based on incidents
    occured up to now

    raises DiagnosticError if any incient detected
    """
    settings = get_plugin_settings(app)

    # CRITERIA 1:
    incidents: Optional[IncidentsRegistry] = app.get(kINCIDENTS_REGISTRY)
    if incidents:

        if not is_sensing_enabled(app):
            # NOTE: this is the only way to avoid accounting
            # before sensing is enabled
            incidents.clear()

        max_delay_allowed: float = settings.DIAGNOSTICS_MAX_TASK_DELAY
        max_delay: float = incidents.max_delay()

        log.debug(
            "Max. blocking delay was %s secs [max allowed %s secs]",
            max_delay,
            max_delay_allowed,
        )

        if max_delay > max_delay_allowed:
            msg = "{:3.1f} secs delay [at most {:3.1f} secs allowed]".format(
                max_delay,
                max_delay_allowed,
            )
            raise HealthCheckFailed(msg)

    # CRITERIA 2: Mean latency of the last N request slower than 1 sec
    probe: Optional[DelayWindowProbe] = app.get(kLATENCY_PROBE)
    if probe:
        latency = probe.value()
        max_latency_allowed = settings.DIAGNOSTICS_MAX_AVG_LATENCY

        log.debug(
            "Mean slow latency of last requests is %s secs [max allowed %s secs]",
            latency,
            max_latency_allowed,
        )

        if max_latency_allowed < latency:
            raise HealthCheckFailed(
                f"Last requests average latency is {latency} secs and surpasses {max_latency_allowed} secs"
            )
