"""
Extension helping to deal with the long running tasks.
Sets up all the infrastructure required to define long running tasks
in a FastAPI application.
The server only has to return a `TaskId` in the handler creating the long
running task. The client will take care of recovering the result from it.
"""

from ...long_running_tasks._errors import TaskAlreadyRunningError, TaskCancelledError
from ...long_running_tasks._task import (
    TaskId,
    TaskProgress,
    TaskResult,
    TasksManager,
    TaskStatus,
    start_task,
)
from ._dependencies import get_tasks_manager
from ._server import setup

__all__: tuple[str, ...] = (
    "get_tasks_manager",
    "setup",
    "start_task",
    "TaskAlreadyRunningError",
    "TaskCancelledError",
    "TaskId",
    "TasksManager",
    "TaskProgress",
    "TaskResult",
    "TaskStatus",
)

# nopycln: file
