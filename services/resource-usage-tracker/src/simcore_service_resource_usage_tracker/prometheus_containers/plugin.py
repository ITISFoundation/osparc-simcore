import logging
from typing import Awaitable, Callable

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.redis_utils import exclusive
from settings_library.prometheus import PrometheusSettings

from ..core.settings import ApplicationSettings
from ..modules.redis import get_redis_client
from .core import collect_container_resource_usage_task

_TASK_NAME = "periodic_prometheus_polling"

_logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        app.state.resource_tracker_task = None
        settings: PrometheusSettings | None = (
            app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
        )
        if not settings:
            _logger.warning("Prometheus API client is de-activated in the settings")
            return
        lock_key = f"{app.title}:collect_container_resource_usage_task_lock"
        lock_value = "locked"
        app.state.resource_tracker_task = start_periodic_task(
            exclusive(get_redis_client(app), lock_key=lock_key, lock_value=lock_value)(
                collect_container_resource_usage_task
            ),
            interval=app_settings.RESOURCE_USAGE_TRACKER_EVALUATION_INTERVAL_SEC,
            task_name=_TASK_NAME,
            app=app,
        )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        if app.state.resource_tracker_task:
            await stop_periodic_task(app.state.resource_tracker_task)

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
