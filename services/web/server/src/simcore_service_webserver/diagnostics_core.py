import logging
import statistics
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


class HealthError(Exception):
    pass


class IncidentsRegistry(LimitedOrderedStack[SlowCallback]):
    def max_delay(self) -> float:
        return self.max_item.delay_secs if self else 0


@attr.s(auto_attribs=True)
class DelayWindowProbe:
    """
        Collects a window of delay samples that satisfy 
        some conditions (see observe code)
    """

    min_threshold_secs: int = 1
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

def assert_healthy_app(app: web.Application) -> None:
    """ Diagnostics function that determins whether
        current application is healthy based on incidents
        occured up to now

        raises DiagnosticError if any incient detected
    """
    incidents: Optional[IncidentsRegistry] = app.get(kINCIDENTS_REGISTRY)
    if incidents:
        max_delay_allowed: float = app[kMAX_TASK_DELAY]
        max_delay: float = incidents.max_delay()

        # criteria 1:
        if max_delay > max_delay_allowed:
            msg = "{:3.1f} secs delay [at most {:3.1f} secs allowed]".format(
                max_delay, max_delay_allowed,
            )
            raise HealthError(msg)

        # TODO: add more criteria

    # CRITERIA 2: Mean latency of the last N request slower than 1 sec
    probe: Optional[DelayWindowProbe] = app.get(kLATENCY_PROBE)
    if probe:
        latency = probe.value()
        max_latency_allowed = app.get(kMAX_AVG_RESP_LATENCY, 4)
        if max_latency_allowed < latency:
            raise HealthError(
                f"Last requests average latency is {latency} secs and surpasses {max_latency_allowed} secs"
            )
