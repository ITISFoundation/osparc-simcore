"""
Extension helping to deal with the long running tasks.
Sets up all the infrastructure required to define long running tasks
in a AIOHTTP application.
The server only has to return a `TaskId` in the handler creating the long
running task.
"""

from ...long_running_tasks._task import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskId,
    TaskManager,
    TaskProgress,
    TaskResult,
    TaskStatus,
    start_task,
)
from ...long_running_tasks._models import CancelResult
from ._dependencies import get_task_manager
from ._server import setup

__all__: tuple[str, ...] = (
    "CancelResult",
    "get_task_manager",
    "setup",
    "start_task",
    "TaskAlreadyRunningError",
    "TaskCancelledError",
    "TaskId",
    "TaskManager",
    "TaskProgress",
    "TaskResult",
    "TaskStatus",
)
