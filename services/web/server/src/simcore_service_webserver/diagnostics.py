
import logging
import os
from typing import List, Optional

import attr
from aiohttp import web

from servicelib import monitor_slow_callbacks

log = logging.getLogger(__name__)

INCIDENTS_REGISTRY_KEY = f"{__name__}.registry"

AIODEBUG_SLOW_DURATION_SECS = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.2))
MAX_DELAY_SECS_ALLOWED = 300 * AIODEBUG_SLOW_DURATION_SECS

@attr.s(auto_attribs=True)
class IncidentsRegistry:
    # FIXME: this needs a limit to keep worst cases?
    slow_callbaks: List[monitor_slow_callbacks.Incident]

    def eval_max_delay(self) -> float:
        return max( incident.delay_secs for incident in self.slow_callbaks )



def setup_diagnostics(app: web.Application, *, max_delay_allowed: Optional[float]=None):
    # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
    if max_delay_allowed is None:
        max_delay_allowed = MAX_DELAY_SECS_ALLOWED
    incidents = monitor_slow_callbacks.enable(max_delay_allowed)

    app[INCIDENTS_REGISTRY_KEY] = IncidentsRegistry(incidents)
