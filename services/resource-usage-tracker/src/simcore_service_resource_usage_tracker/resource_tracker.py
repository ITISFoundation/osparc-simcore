from typing import Awaitable, Callable

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task

from .core.settings import ApplicationSettings
from .resource_tracker_core import evaluate_service_resource_usage

_TASK_NAME = "periodic_prometheus_polling"


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings

        app.state.autoscaler_task = start_periodic_task(
            evaluate_service_resource_usage,
            interval=app_settings.RESOURCE_USAGE_TRACKER_EVALUATION_INTERVAL_SEC,
            task_name=_TASK_NAME,
            app=app,
        )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        await stop_periodic_task(app.state.autoscaler_task)

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
