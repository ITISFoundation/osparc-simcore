import asyncio.events
import time
import sys
from typing import List

from pyinstrument import Profiler

from .incidents import SlowCallback


def enable(slow_duration_secs: float, incidents: List[SlowCallback]) -> None:
    """Based in from aiodebug

    Patches ``asyncio.events.Handle`` to report an incident every time a callback
    takes ``slow_duration_secs`` seconds or more to run.
    """
    # pylint: disable=protected-access
    from aiodebug.logging_compat import get_logger

    logger = get_logger(__name__)
    _run = asyncio.events.Handle._run

    def instrumented(self):
        # unsetting profiler, helps with development mode and tests
        sys.setprofile(None)

        with Profiler(interval=slow_duration_secs) as profiler:
            t0 = time.monotonic()

            retval = _run(self)

            dt = time.monotonic() - t0

            profiler_result = profiler.output_text(unicode=True, color=False, show_all=True)

        slow_callbacks_detected = "No samples were recorded." not in profiler_result

        if slow_callbacks_detected:
            incidents.append(SlowCallback(msg=profiler_result, delay_secs=dt))
            logger.warning("Executing took %.3f seconds\n%s", dt, profiler_result)
        return retval

    asyncio.events.Handle._run = instrumented
