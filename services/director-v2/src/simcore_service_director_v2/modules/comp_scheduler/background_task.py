import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from typing import Any, Callable, Coroutine

from fastapi import FastAPI

from . import _factory

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S: int = 5


async def scheduler_task(app: FastAPI) -> None:
    scheduler = app.state.scheduler
    while app.state.is_comp_scheduler_running:
        try:
            logger.debug("Computational scheduler task running...")
            await scheduler.schedule_all_pipelines()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    scheduler.wake_up_event.wait(), timeout=_DEFAULT_TIMEOUT_S
                )
        except CancelledError:
            logger.info("Computational scheduler task cancelled")
            raise
        except Exception:  # pylint: disable=broad-except
            if not app.state.is_comp_scheduler_running:
                logger.warning("Forced to stop computational scheduler")
                break
            logger.exception(
                "Unexpected error in computational scheduler task, restarting scheduler now..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(_DEFAULT_TIMEOUT_S)


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        # FIXME: added this variable to overcome the state in which the
        # task cancelation is ignored and the exceptions enter in a loop
        # that never stops the background task. This flag is an additional
        # mechanism to enforce stopping the background task
        app.state.is_comp_scheduler_running = True
        app.state.scheduler = await _factory.create_from_db(app)
        app.state.scheduler_task = asyncio.create_task(
            scheduler_task(app), name="computational services scheduler"
        )
        logger.info("Computational services Scheduler started")

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        logger.info("Computational services Scheduler stopping...")
        task = app.state.scheduler_task
        with suppress(CancelledError):
            app.state.is_comp_scheduler_running = False
            task.cancel()
            await task
        app.state.scheduler = None
        app.state.scheduler_task = None
        logger.info("Computational services Scheduler stopped")

    return stop_scheduler


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
