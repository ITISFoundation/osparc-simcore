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
    TaskProgress,
    TaskProtocol,
    TasksManager,
    TaskStatus,
    start_task,
)
from ._dependencies import create_task_name_from_request, get_tasks_manager
from ._routes import TaskGet
from ._server import setup

__all__: tuple[str, ...] = (
    "create_task_name_from_request",
    "get_tasks_manager",
    "setup",
    "start_task",
    "TaskAlreadyRunningError",
    "TaskCancelledError",
    "TaskId",
    "TaskGet",
    "TasksManager",
    "TaskProgress",
    "TaskProtocol",
    "TaskStatus",
)

# nopycln: file
