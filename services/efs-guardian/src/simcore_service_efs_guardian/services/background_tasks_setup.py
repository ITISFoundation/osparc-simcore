import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypedDict

from fastapi import FastAPI
from servicelib.async_utils import cancel_wait_task
from servicelib.logging_utils import log_catch, log_context

from .background_tasks import removal_policy_task

_logger = logging.getLogger(__name__)


class EfsGuardianBackgroundTask(TypedDict):
    name: str
    task_func: Callable


_EFS_GUARDIAN_BACKGROUND_TASKS = [
    EfsGuardianBackgroundTask(
        name="efs_removal_policy_task", task_func=removal_policy_task
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
                    asyncio.create_task(task["task_func"](), name=task["name"])
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
