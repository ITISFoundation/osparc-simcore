import asyncio.events
import sys
import time

from pyinstrument import Profiler

from .incidents import LimitedOrderedStack, SlowCallback


def enable(
    slow_duration_secs: float, incidents: LimitedOrderedStack[SlowCallback]
) -> None:
    """Based in from aiodebug

    Patches ``asyncio.events.Handle`` to report an incident every time a callback
    takes ``slow_duration_secs`` seconds or more to run.
    """
    # pylint: disable=protected-access
    from aiodebug.logging_compat import get_logger

    aio_debug_logger = get_logger(__name__)
    _run = asyncio.events.Handle._run

    def instrumented(self):
        # unsetting profiler, helps with development mode and tests
        sys.setprofile(None)

        with Profiler(interval=slow_duration_secs) as profiler:
            t0 = time.monotonic()

            retval = _run(self)

            dt = time.monotonic() - t0

        if dt >= slow_duration_secs:
            # the indentation is correct, the profiler needs to be stopped when
            # printing the output, the profiler is started and stopped by the
            # contextmanger
            profiler_result = profiler.output_text(
                unicode=True, color=False, show_all=True
            )
            incidents.append(SlowCallback(msg=profiler_result, delay_secs=dt))
            aio_debug_logger.warning(
                "Executing took %.3f seconds\n%s", dt, profiler_result
            )

        return retval

    asyncio.events.Handle._run = instrumented  # type: ignore[method-assign]
