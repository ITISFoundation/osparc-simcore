import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TypedDict

from fastapi import FastAPI
from servicelib.background_task import stop_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.redis_utils import start_exclusive_periodic_task

from .background_tasks import removal_policy_task
from .modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)


class EfsGuardianBackgroundTask(TypedDict):
    name: str
    task_func: Callable


_EFS_GUARDIAN_BACKGROUND_TASKS = [
    EfsGuardianBackgroundTask(
        name="efs_removal_policy_task", task_func=removal_policy_task
    )
]


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with log_context(
            _logger, logging.INFO, msg="Efs Guardian startup.."
        ), log_catch(_logger, reraise=False):
            app.state.efs_guardian_background_tasks = []

            # Setup periodic tasks
            for task in _EFS_GUARDIAN_BACKGROUND_TASKS:
                exclusive_task = start_exclusive_periodic_task(
                    get_redis_lock_client(app),
                    task["task_func"],
                    task_period=timedelta(seconds=60),  # 1 minute
                    retry_after=timedelta(seconds=60),  # 5 minutes
                    task_name=task["name"],
                    app=app,
                )
                app.state.efs_guardian_background_tasks.append(exclusive_task)

    return _startup


def on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with log_context(
            _logger, logging.INFO, msg="Efs Guardian shutdown.."
        ), log_catch(_logger, reraise=False):
            assert _app  # nosec
            if _app.state.efs_guardian_background_tasks:
                await asyncio.gather(
                    *[
                        stop_periodic_task(task)
                        for task in _app.state.efs_guardian_background_tasks
                    ]
                )

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
