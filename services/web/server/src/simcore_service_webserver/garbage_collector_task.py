""" Setup and running of periodic background task


Specifics of the gc implementation should go into garbage_collector_core.py
"""

import asyncio
import logging

from aiohttp import web

from .garbage_collector_core import collect_garbage
from .garbage_collector_settings import GarbageCollectorSettings, get_plugin_settings

logger = logging.getLogger(__name__)


GC_TASK_NAME = f"background-task.{__name__}.collect_garbage_periodically"
GC_TASK_CONFIG = f"{GC_TASK_NAME}.config"


async def run_background_task(app: web.Application):
    # SETUP ------
    # create a background task to collect garbage periodically
    assert not any(  # nosec
        t.get_name() == GC_TASK_NAME for t in asyncio.all_tasks()
    ), "Garbage collector task already running. ONLY ONE expected"  # nosec

    gc_bg_task = asyncio.create_task(
        collect_garbage_periodically(app), name=GC_TASK_NAME
    )

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

    while True:
        logger.info("Starting garbage collector...")
        try:
            interval = settings.GARBAGE_COLLECTOR_INTERVAL_S
            while True:
                await collect_garbage(app)

                if app[GC_TASK_CONFIG].get("force_stop", False):
                    raise Exception("Forced to stop garbage collection")

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Garbage collection task was cancelled, it will not restart!")
            # do not catch Cancellation errors
            raise

        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "There was an error during garbage collection, restarting...",
                exc_info=True,
            )

            if app[GC_TASK_CONFIG].get("force_stop", False):
                logger.warning("Forced to stop garbage collection")
                break

            # will wait 5 seconds to recover before restarting to avoid restart loops
            # - it might be that db/redis is down, etc
            #
            await asyncio.sleep(5)
