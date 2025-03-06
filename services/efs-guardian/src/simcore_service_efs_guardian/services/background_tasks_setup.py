import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TypedDict

from fastapi import FastAPI
from servicelib.async_utils import cancel_wait_task
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_catch, log_context

from .background_tasks import removal_policy_task
from .modules.redis import get_redis_lock_client


@exclusive_periodic(
    get_redis_lock_client,
    task_interval=timedelta(hours=1),
    retry_after=timedelta(minutes=5),
)
async def periodic_removal_policy_task(app: FastAPI) -> None:
    await removal_policy_task(app)


_logger = logging.getLogger(__name__)


class EfsGuardianBackgroundTask(TypedDict):
    name: str
    task_func: Callable


_EFS_GUARDIAN_BACKGROUND_TASKS = [
    EfsGuardianBackgroundTask(
        name="efs_removal_policy_task", task_func=periodic_removal_policy_task
    )
]


def _on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with (
            log_context(_logger, logging.INFO, msg="Efs Guardian startup.."),
            log_catch(_logger, reraise=False),
        ):
            app.state.efs_guardian_background_tasks = []

            # Setup periodic tasks
            for task in _EFS_GUARDIAN_BACKGROUND_TASKS:
                app.state.efs_guardian_background_tasks.append(
                    await asyncio.create_task(task["task_func"](), name=task["name"])
                )

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with (
            log_context(_logger, logging.INFO, msg="Efs Guardian shutdown.."),
            log_catch(_logger, reraise=False),
        ):
            assert _app  # nosec
            if _app.state.efs_guardian_background_tasks:
                await asyncio.gather(
                    *[
                        cancel_wait_task(task)
                        for task in _app.state.efs_guardian_background_tasks
                    ]
                )

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", _on_app_startup(app))
    app.add_event_handler("shutdown", _on_app_shutdown(app))
