import asyncio
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .garbage_collector_core import (
    MODULE_LOGGER_NAME,
    TASK_CONFIG,
    TASK_NAME,
    collect_garbage_periodically,
)

logger = logging.getLogger(MODULE_LOGGER_NAME)


async def _start_background_task(app: web.Application):
    # SETUP ------
    # create a background task to collect garbage periodically
    assert not any(  # nosec
        t.get_name() == TASK_NAME for t in asyncio.all_tasks()
    ), "Garbage collector task already running. ONLY ONE expected"  # nosec

    gc_bg_task = asyncio.create_task(collect_garbage_periodically(app), name=TASK_NAME)

    # FIXME: added this config to overcome the state in which the
    # task cancelation is ignored and the exceptions enter in a loop
    # that never stops the background task. This flag is an additional
    # mechanism to enforce stopping the background task
    #
    # Implemented with a mutable dict to avoid
    #   DeprecationWarning: Changing state of started or joined application is deprecated
    #
    app[TASK_CONFIG] = {"force_stop": False, "name": TASK_NAME}

    yield

    # TEAR-DOWN -----
    # controlled cancelation of the gc task
    try:
        logger.info("Stopping garbage collector...")

        ack = gc_bg_task.cancel()
        assert ack  # nosec

        app[TASK_CONFIG]["force_stop"] = True

        await gc_bg_task

    except asyncio.CancelledError:
        assert gc_bg_task.cancelled()  # nosec


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GARBAGE_COLLECTOR",
    logger=logger,
)
def setup_garbage_collector(app: web.Application):
    app.cleanup_ctx.append(_start_background_task)
