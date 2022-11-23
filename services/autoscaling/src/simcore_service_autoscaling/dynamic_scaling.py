import logging
from typing import Awaitable, Callable

from fastapi import FastAPI

from .background_task import start_background_task, stop_background_task
from .core.settings import ApplicationSettings
from .dynamic_scaling_core import check_dynamic_resources

_TASK_NAME = "Autoscaling AWS EC2 instances"

logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        app.state.autoscaler_task = await start_background_task(
            check_dynamic_resources,
            interval=app_settings.AUTOSCALING_POLL_INTERVAL,
            task_name=_TASK_NAME,
            app=app,
        )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        await stop_background_task(app.state.autoscaler_task)

    return _stop


def setup(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings
    if any(
        s is None
        for s in [
            app_settings.AUTOSCALING_NODES_MONITORING,
            app_settings.AUTOSCALING_EC2_ACCESS,
            app_settings.AUTOSCALING_EC2_INSTANCES,
        ]
    ):
        logger.warning(
            "the autoscaling background task is disabled by settings, nothing will happen!"
        )
        return
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
