import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypedDict

from fastapi import FastAPI
from servicelib.background_task import stop_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.redis_utils import start_exclusive_periodic_task

from ..core.settings import ApplicationSettings
from .background_task_periodic_heartbeat_check import (
    periodic_check_of_running_services_task,
)
from .modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)

_TASK_NAME_PERIODICALY_CHECK_RUNNING_SERVICES = "periodic_check_of_running_services"


class RutBackgroundTask(TypedDict):
    name: str
    task_func: Callable


_RUT_BACKGROUND_TASKS = [
    RutBackgroundTask(
        name=_TASK_NAME_PERIODICALY_CHECK_RUNNING_SERVICES,
        task_func=periodic_check_of_running_services_task,
    )
]


def _on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with log_context(
            _logger, logging.INFO, msg="RUT background tasks startup.."
        ), log_catch(_logger, reraise=False):
            app_settings: ApplicationSettings = app.state.settings

            app.state.rut_background_tasks = []

            # Setup periodic tasks
            for task in _RUT_BACKGROUND_TASKS:
                exclusive_task = start_exclusive_periodic_task(
                    get_redis_lock_client(app),
                    task["task_func"],
                    task_period=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
                    retry_after=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
                    task_name=task["name"],
                    app=app,
                )
                app.state.rut_background_tasks.append(exclusive_task)

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with log_context(
            _logger, logging.INFO, msg="RUT background tasks shutdown.."
        ), log_catch(_logger, reraise=False):
            assert _app  # nosec
            if _app.state.rut_background_tasks:
                await asyncio.gather(
                    *[
                        stop_periodic_task(task)
                        for task in _app.state.rut_background_tasks
                    ]
                )

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", _on_app_startup(app))
    app.add_event_handler("shutdown", _on_app_shutdown(app))
