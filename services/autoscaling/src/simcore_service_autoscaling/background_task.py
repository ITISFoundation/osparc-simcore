import asyncio
import contextlib
import datetime
import logging
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from .core.settings import ApplicationSettings
from .dynamic_scaling import check_dynamic_resources

logger = logging.getLogger(__name__)


_TASK_NAME = "Autoscaler background task"


async def _repeated_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: Optional[str] = None,
    **kwargs,
):
    if not task_name:
        task_name = task.__name__
    while await asyncio.sleep(interval.total_seconds(), result=True):
        try:
            with log_context(logger, logging.DEBUG, msg=f"Run {task_name}"):
                await task(**kwargs)
        except asyncio.CancelledError:
            logger.info("%s cancelled", task_name)
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error in %s, restarting...", task_name)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def start_auto_scaler_task() -> None:
        app_settings: ApplicationSettings = app.state.settings
        with log_context(logger, logging.INFO, msg=f"create {_TASK_NAME}"):
            app.state.autoscaler_task = asyncio.create_task(
                _repeated_scheduled_task(
                    check_dynamic_resources,
                    interval=app_settings.AUTOSCALING_POLL_INTERVAL,
                    task_name=_TASK_NAME,
                    app=app,
                ),
                name=f"{_TASK_NAME}",
            )

    return start_auto_scaler_task


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def stop_auto_scaler_task() -> None:
        with log_context(logger, logging.INFO, msg=f"remove {_TASK_NAME}"):
            task: asyncio.Task = app.state.autoscaler_task
            with contextlib.suppress(asyncio.CancelledError):
                task.cancel()
                await task

    return stop_auto_scaler_task


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
