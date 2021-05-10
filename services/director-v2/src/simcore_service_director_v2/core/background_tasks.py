import asyncio
import logging
from typing import Callable

from fastapi import FastAPI

from ..modules.scheduler import scheduler_task

logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable:
    async def start_background_tasks() -> None:
        logger.info("Starting background tasks")

        if app.state.settings.scheduler.enabled:
            await start_scheduler_task(app)

    return start_background_tasks


def on_app_shutdown(app: FastAPI) -> Callable:
    async def stop_background_tasks() -> None:
        logger.info("Stopping background tasks")

        if app.state.settings.scheduler.enabled:
            await stop_scheduler_task(app)

    return stop_background_tasks


async def start_scheduler_task(app: FastAPI) -> None:
    task = asyncio.get_event_loop().create_task(scheduler_task(app))
    app.state.scheduler_task = task


async def stop_scheduler_task(app: FastAPI) -> None:
    task = app.state.scheduler_task
    task.cancel()
    await task
