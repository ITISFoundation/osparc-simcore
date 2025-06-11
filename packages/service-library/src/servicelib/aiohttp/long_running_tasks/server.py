"""
Extension helping to deal with the long running tasks.
Sets up all the infrastructure required to define long running tasks
in a AIOHTTP application.
The server only has to return a `TaskId` in the handler creating the long
running task.
"""

from ._dependencies import get_tasks_manager
from ._routes import get_task_context
from ._server import setup, start_long_running_task

__all__: tuple[str, ...] = (
    "get_task_context",
    "get_tasks_manager",
    "setup",
    "start_long_running_task",
)

# nopycln: file
