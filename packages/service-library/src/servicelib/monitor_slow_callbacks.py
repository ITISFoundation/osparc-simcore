
# Based in from aiodebug

import asyncio.events
import time
from asyncio.base_events import _format_handle
from typing import List

import attr


@attr.s(auto_attribs=True)
class Incident:
    msg: str
    delay_secs: float


def enable(slow_duration_secs: float) -> List[Incident]:
    """

	Patch ``asyncio.events.Handle`` to log warnings every time a callback
    takes ``slow_duration_secs`` seconds or more to run.
	"""
    # pylint: disable=protected-access
    from aiodebug.logging_compat import get_logger

    indicents: List[Incident] = []

    logger = get_logger(__name__)
    _run = asyncio.events.Handle._run

    def instrumented(self):
        t0 = time.monotonic()
        retval = _run(self)
        dt = time.monotonic() - t0
        if dt >= slow_duration_secs:
            task_info = _format_handle(self)
            indicents.append( Incident(task_info, dt) )
            logger.warning("Executing %s took %.3f seconds", task_info, dt)
        return retval

    asyncio.events.Handle._run = instrumented
    return indicents
