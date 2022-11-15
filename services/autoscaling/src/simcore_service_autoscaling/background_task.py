import asyncio
import contextlib
import logging
from typing import Awaitable, Callable

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from .core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


_TASK_NAME = "Autoscaler background task"


async def auto_scaler_task(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings
    while await asyncio.sleep(
        app_settings.AUTOSCALING_POLL_INTERVAL.total_seconds(), result=True
    ):
        try:
            with log_context(logger, logging.DEBUG, msg=f"Run {_TASK_NAME}"):
                ...
        except asyncio.CancelledError:
            logger.info("%s cancelled", _TASK_NAME)
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error in %s, restarting...", _TASK_NAME)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def start_auto_scaler_task() -> None:
        with log_context(logger, logging.INFO, msg=f"create {_TASK_NAME}"):
            app.state.auto_scaler_task = asyncio.create_task(
                auto_scaler_task(app), name=f"{_TASK_NAME}"
            )

    return start_auto_scaler_task


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def stop_auto_scaler_task() -> None:
        with log_context(logger, logging.INFO, msg=f"remove {_TASK_NAME}"):
            task: asyncio.Task = app.state.auto_scaler_task
            with contextlib.suppress(asyncio.CancelledError):
                task.cancel()
                await task

    return stop_auto_scaler_task


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
