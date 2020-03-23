
import os
from typing import List

import attr
from aiohttp import web
import logging

from servicelib import monitor_slow_callbacks

log = logging.getLogger(__name__)

INCIDENTS_REGISTRY_KEY = f"{__name__}.registry"

AIODEBUG_SLOW_DURATION_SECS = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.1))
MAX_DELAY_SECS_ALLOWED = 300 * AIODEBUG_SLOW_DURATION_SECS

@attr.s(auto_attribs=True)
class IncidentsRegistry:
    slow_callbaks: List[monitor_slow_callbacks.Incident]

    @property
    def max_delay(self) -> float:
        return max( incident.delay_secs for incident in self.slow_callbaks )



def setup_diagnostics(app: web.Application):
    # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
    incidents = monitor_slow_callbacks.enable(MAX_DELAY_SECS_ALLOWED)

    app[INCIDENTS_REGISTRY_KEY] = IncidentsRegistry(incidents)
