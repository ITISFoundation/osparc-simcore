import logging
import os
from operator import attrgetter
from typing import Optional

from aiohttp import web

from servicelib import monitor_slow_callbacks
from servicelib.incidents import LimitedOrderedStack, SlowCallback

log = logging.getLogger(__name__)


class DiagnosticError(Exception):
    pass


class IncidentsRegistry(LimitedOrderedStack[SlowCallback]):
    def max_delay(self) -> float:
        return self.max_item.delay_secs if self else 0


def assert_healthy_app(app: web.Application) -> None:
    """ Diagnostics function that determins whether
        current application is healthy based on incidents
        occured up to now

        raises DiagnosticError if any incient detected
    """
    incidents: Optional[IncidentsRegistry] = app.get(f"{__name__}.registry")
    if incidents:
        max_delay_allowed: float = app[f"{__name__}.max_delay_allowed"]
        max_delay: float = incidents.max_delay()

        # criteria 1:
        if max_delay > max_delay_allowed:
            msg = "{:3.1f} secs delay [at most {:3.1f} secs allowed]".format(
                max_delay, max_delay_allowed,
            )
            raise DiagnosticError(msg)

        # TODO: add more criteria


def setup_diagnostics(
    app: web.Application,
    *,
    slow_duration_secs: Optional[float] = None,
    max_delay_allowed: Optional[float] = None,
):

    if slow_duration_secs is None:
        # blocking time to be considered an incident
        slow_duration_secs = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.2))

    if max_delay_allowed is None:
        # blocking time to consider app unhealthy
        max_delay_allowed = max(10 * slow_duration_secs, 30)  # secs

    log.info("slow_duration_secs = %3.2f secs", slow_duration_secs)
    log.info("max_delay_allowed = %3.2f secs", max_delay_allowed)

    # TODO: delay_secs should be automatic
    registry = IncidentsRegistry(order_by=attrgetter("delay_secs"))

    # calls are registered with add(incident)
    monitor_slow_callbacks.enable(max_delay_allowed, registry)

    app[f"{__name__}.registry"] = registry
    app[f"{__name__}.max_delay_allowed"] = max_delay_allowed
