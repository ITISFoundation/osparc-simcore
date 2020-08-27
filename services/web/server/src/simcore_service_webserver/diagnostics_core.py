import logging
import statistics
import time
from typing import List, Optional

import attr
from aiohttp import web

from servicelib.incidents import LimitedOrderedStack, SlowCallback

log = logging.getLogger(__name__)

# APP KEYS ---
kINCIDENTS_REGISTRY = f"{__name__}.incidents_registry"
kLAST_REQUESTS_AVG_LATENCY = f"{__name__}.last_requests_avg_latency"
kMAX_AVG_RESP_LATENCY = f"{__name__}.max_avg_response_latency"
kMAX_TASK_DELAY = f"{__name__}.max_task_delay"

kLATENCY_PROBE = f"{__name__}.latency_probe"
kPLUGIN_START_TIME = f"{__name__}.plugin_start_time"

kSTART_SENSING_DELAY_SECS = f"{__name__}.start_sensing_delay"


class HealthError(Exception):
    """ Service is set as unhealty """


class IncidentsRegistry(LimitedOrderedStack[SlowCallback]):
    def max_delay(self) -> float:
        return self.max_item.delay_secs if self else 0


@attr.s(auto_attribs=True)
class DelayWindowProbe:
    """
        Collects a window of delay samples that satisfy
        some conditions (see observe code)
    """

    min_threshold_secs: int = 0.3
    max_window: int = 100
    last_delays: List = attr.ib(factory=list)

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


def is_sensing_enabled(app: web.Application):
    """ Diagnostics will not activate sensing inmediatly but after some
        time since the app started
    """
    time_elapsed_since_setup = time.time() - app[kPLUGIN_START_TIME]
    enabled = time_elapsed_since_setup > app[kSTART_SENSING_DELAY_SECS]
    if enabled:
        log.debug(
            "Diagnostics starts sensing after waiting %3.2f secs [> %3.2f secs] since submodule init",
            time_elapsed_since_setup,
            app[kSTART_SENSING_DELAY_SECS],
        )
    return enabled


def assert_healthy_app(app: web.Application) -> None:
    """ Diagnostics function that determins whether
        current application is healthy based on incidents
        occured up to now

        raises DiagnosticError if any incient detected
    """
    # CRITERIA 1:
    incidents: Optional[IncidentsRegistry] = app.get(kINCIDENTS_REGISTRY)
    if incidents:

        if not is_sensing_enabled(app):
            # NOTE: this is the only way to avoid accounting
            # before sensing is enabled
            incidents.clear()

        max_delay_allowed: float = app[kMAX_TASK_DELAY]
        max_delay: float = incidents.max_delay()

        log.debug(
            "Max. blocking delay was %s secs [max allowed %s secs]",
            max_delay,
            max_delay_allowed,
        )

        if max_delay > max_delay_allowed:
            msg = "{:3.1f} secs delay [at most {:3.1f} secs allowed]".format(
                max_delay, max_delay_allowed,
            )
            raise HealthError(msg)

    # CRITERIA 2: Mean latency of the last N request slower than 1 sec
    probe: Optional[DelayWindowProbe] = app.get(kLATENCY_PROBE)
    if probe:
        latency = probe.value()
        max_latency_allowed = app.get(kMAX_AVG_RESP_LATENCY, 4)

        log.debug(
            "Mean slow latency of last requests is %s secs [max allowed %s secs]",
            latency,
            max_latency_allowed,
        )

        if max_latency_allowed < latency:
            raise HealthError(
                f"Last requests average latency is {latency} secs and surpasses {max_latency_allowed} secs"
            )
