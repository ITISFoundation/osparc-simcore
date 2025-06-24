import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypedDict

from common_library.async_tools import cancel_and_wait
from fastapi import FastAPI
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_catch, log_context

from ..core.settings import ApplicationSettings
from .background_task_periodic_heartbeat_check import check_running_services
from .modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)


_TASK_NAME_PERIODICALY_CHECK_RUNNING_SERVICES = "periodic_check_of_running_services"


class RutBackgroundTask(TypedDict):
    name: str
    task_func: Callable


def _on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with (
            log_context(
                _logger,
                logging.INFO,
                msg="RUT background task Periodic check of running services startup..",
            ),
            log_catch(_logger, reraise=False),
        ):
            app_settings: ApplicationSettings = app.state.settings

            app.state.rut_background_task__periodic_check_of_running_services = None

            @exclusive_periodic(
                get_redis_lock_client(app),
                task_interval=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
                retry_after=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
            )
            async def _periodic_check_running_services() -> None:
                await check_running_services(app)

            app.state.rut_background_task__periodic_check_of_running_services = (
                asyncio.create_task(
                    _periodic_check_running_services(),
                    name=_TASK_NAME_PERIODICALY_CHECK_RUNNING_SERVICES,
                )
            )

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with (
            log_context(
                _logger,
                logging.INFO,
                msg="RUT background tasks Periodic check of running services shutdown..",
            ),
            log_catch(_logger, reraise=False),
        ):
            assert _app  # nosec
            if _app.state.rut_background_task__periodic_check_of_running_services:
                await cancel_and_wait(
                    _app.state.rut_background_task__periodic_check_of_running_services
                )

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", _on_app_startup(app))
    app.add_event_handler("shutdown", _on_app_shutdown(app))
