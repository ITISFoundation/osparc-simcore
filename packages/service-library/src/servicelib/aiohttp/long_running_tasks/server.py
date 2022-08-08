"""
Extension helping to deal with the long running tasks.
Sets up all the infrastructure required to define long running tasks
in a FastAPI application.
The server only has to return a `TaskId` in the handler creating the long
running task. The client will take care of recovering the result from it.
"""

from ._server import setup
from ._dependencies import get_task_manager
from ...long_running_tasks._task import start_task, TaskProgress

__all__: tuple[str, ...] = (
    "setup",
    "get_task_manager",
    "start_task",
    "TaskAlreadyRunningError",
    "TaskId",
    "TaskManager",
    "TaskProgress",
    "TaskStatus",
)
