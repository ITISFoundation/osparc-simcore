import asyncio.events
import time
from asyncio.base_events import _format_handle
from typing import List

from .incidents import SlowCallback


def enable(slow_duration_secs: float, incidents: List[SlowCallback]) -> None:
    """ Based in from aiodebug

    Patches ``asyncio.events.Handle`` to report an incident every time a callback
    takes ``slow_duration_secs`` seconds or more to run.
    """
    # pylint: disable=protected-access
    from aiodebug.logging_compat import get_logger

    logger = get_logger(__name__)
    _run = asyncio.events.Handle._run

    def instrumented(self):
        t0 = time.monotonic()
        retval = _run(self)
        dt = time.monotonic() - t0
        if dt >= slow_duration_secs:
            task_info = _format_handle(self)
            incidents.append(SlowCallback(msg=task_info, delay_secs=dt))
            logger.warning("Executing %s took %.3f seconds", task_info, dt)
        return retval

    asyncio.events.Handle._run = instrumented
