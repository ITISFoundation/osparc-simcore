""" Setup and running of periodic background task


Specifics of the gc implementation should go into garbage_collector_core.py
"""

import asyncio
import logging

from aiohttp import web
from servicelib.logging_utils import log_context

from .garbage_collector_core import collect_garbage
from .garbage_collector_settings import GarbageCollectorSettings, get_plugin_settings

logger = logging.getLogger(__name__)


GC_TASK_NAME = f"background-task.{__name__}.collect_garbage_periodically"
GC_TASK_CONFIG = f"{GC_TASK_NAME}.config"
GC_TASK = f"{GC_TASK_NAME}.task"


async def run_background_task(app: web.Application):
    # SETUP ------
    # create a background task to collect garbage periodically
    assert not any(  # nosec
        t.get_name() == GC_TASK_NAME for t in asyncio.all_tasks()
    ), "Garbage collector task already running. ONLY ONE expected"  # nosec

    gc_bg_task = asyncio.create_task(
        collect_garbage_periodically(app), name=GC_TASK_NAME
    )
    # attaches variable to the app's lifetime
    app[GC_TASK] = gc_bg_task

    # FIXME: added this config to overcome the state in which the
    # task cancelation is ignored and the exceptions enter in a loop
    # that never stops the background task. This flag is an additional
    # mechanism to enforce stopping the background task
    #
    # Implemented with a mutable dict to avoid
    #   DeprecationWarning: Changing state of started or joined application is deprecated
    #
    app[GC_TASK_CONFIG] = {"force_stop": False, "name": GC_TASK_NAME}

    yield

    # TEAR-DOWN -----
    # controlled cancelation of the gc task
    try:
        logger.info("Stopping garbage collector...")

        ack = gc_bg_task.cancel()
        assert ack  # nosec

        app[GC_TASK_CONFIG]["force_stop"] = True

        await gc_bg_task

    except asyncio.CancelledError:
        assert gc_bg_task.cancelled()  # nosec


async def collect_garbage_periodically(app: web.Application):
    settings: GarbageCollectorSettings = get_plugin_settings(app)
    interval = settings.GARBAGE_COLLECTOR_INTERVAL_S

    while True:
        try:
            while True:
                with log_context(logger, logging.INFO, "Garbage collect cycle"):
                    await collect_garbage(app)

                    if app[GC_TASK_CONFIG].get("force_stop", False):
                        raise RuntimeError("Forced to stop garbage collection")

                logger.info("Garbage collect cycle pauses %ss", interval)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:  # EXIT
            logger.info(
                "Stopped: Garbage collection task was cancelled, it will not restart!"
            )
            # do not catch Cancellation errors
            raise

        except Exception:  # RESILIENT restart # pylint: disable=broad-except
            logger.warning(
                "Stopped: There was an error during garbage collection, restarting...",
                exc_info=True,
            )

            if app[GC_TASK_CONFIG].get("force_stop", False):
                logger.warning("Forced to stop garbage collection")
                break

            # will wait 5 seconds to recover before restarting to avoid restart loops
            # - it might be that db/redis is down, etc
            #
            await asyncio.sleep(5)
