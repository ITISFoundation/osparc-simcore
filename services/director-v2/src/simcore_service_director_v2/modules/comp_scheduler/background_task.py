import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from typing import Any, Callable, Coroutine

from fastapi import FastAPI

from . import factory
from .base_scheduler import BaseCompScheduler

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S: int = 5


async def scheduler_task(scheduler: BaseCompScheduler, run_scheduler: bool) -> None:
    while run_scheduler:
        try:
            logger.debug("scheduler task running...")
            await scheduler.schedule_all_pipelines()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    scheduler.wake_up_event.wait(), timeout=_DEFAULT_TIMEOUT_S
                )
        except CancelledError:
            logger.info("scheduler task cancelled")
            raise
        except Exception:  # pylint: disable=broad-except
            if not run_scheduler:
                break
            logger.exception(
                "Unexpected error in scheduler task, restarting scheduler now..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(_DEFAULT_TIMEOUT_S)


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        app.state.comp_scheduler_running = run_scheduler = True
        app.state.scheduler = scheduler = await factory.create_from_db(app)
        app.state.scheduler_task = asyncio.create_task(
            scheduler_task(scheduler, run_scheduler), name="comp. services scheduler"
        )
        logger.info("Computational services Scheduler started")

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        app.state.comp_scheduler_running = False
        task = app.state.scheduler_task
        app.state.scheduler = None
        with suppress(CancelledError):
            task.cancel()
            await task
        app.state.scheduler_task = None
        logger.info("Computational services Scheduler stopped")

    return stop_scheduler


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
