"""Setup and running of periodic background task


Specifics of the gc implementation should go into garbage_collector_core.py
"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from aiohttp import web
from common_library.async_tools import cancel_and_wait
from servicelib.logging_utils import log_context

from ._core import collect_garbage
from .settings import GarbageCollectorSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


_GC_TASK_NAME = f"background-task.{__name__}.collect_garbage_periodically"
_GC_TASK_CONFIG = f"{_GC_TASK_NAME}.config"
_GC_TASK = f"{_GC_TASK_NAME}.task"


async def run_background_task(app: web.Application) -> AsyncGenerator:
    # SETUP ------
    # create a background task to collect garbage periodically
    assert not any(  # nosec
        t.get_name() == _GC_TASK_NAME for t in asyncio.all_tasks()
    ), "Garbage collector task already running. ONLY ONE expected"  # nosec

    gc_bg_task = asyncio.create_task(
        _collect_garbage_periodically(app), name=_GC_TASK_NAME
    )
    # attaches variable to the app's lifetime
    app[_GC_TASK] = gc_bg_task

    # FIXME: added this config to overcome the state in which the
    # task cancelation is ignored and the exceptions enter in a loop
    # that never stops the background task. This flag is an additional
    # mechanism to enforce stopping the background task
    #
    # Implemented with a mutable dict to avoid
    #   DeprecationWarning: Changing state of started or joined application is deprecated
    #
    app[_GC_TASK_CONFIG] = {"force_stop": False, "name": _GC_TASK_NAME}

    yield

    # TEAR-DOWN -----
    # controlled cancelation of the gc task
    _logger.info("Stopping garbage collector...")

    ack = gc_bg_task.cancel()
    assert ack  # nosec

    app[_GC_TASK_CONFIG]["force_stop"] = True

    await cancel_and_wait(gc_bg_task)


async def _collect_garbage_periodically(app: web.Application):
    settings: GarbageCollectorSettings = get_plugin_settings(app)
    interval = settings.GARBAGE_COLLECTOR_INTERVAL_S

    while True:
        try:
            while True:
                with log_context(_logger, logging.INFO, "Garbage collect cycle"):
                    await collect_garbage(app)

                    if app[_GC_TASK_CONFIG].get("force_stop", False):
                        msg = "Forced to stop garbage collection"
                        raise RuntimeError(msg)

                _logger.info("Garbage collect cycle pauses %ss", interval)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:  # EXIT  # noqa: PERF203
            _logger.info(
                "Stopped: Garbage collection task was cancelled, it will not restart!"
            )
            # do not catch Cancellation errors
            raise

        except Exception:  # RESILIENT restart # pylint: disable=broad-except
            _logger.warning(
                "Stopped: There was an error during garbage collection, restarting...",
                exc_info=True,
            )

            if app[_GC_TASK_CONFIG].get("force_stop", False):
                _logger.warning("Forced to stop garbage collection")
                break

            # will wait 5 seconds to recover before restarting to avoid restart loops
            # - it might be that db/redis is down, etc
            #
            await asyncio.sleep(5)
