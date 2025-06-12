"""
Extension helping to deal with the long running tasks.
Sets up all the infrastructure required to define long running tasks
in a AIOHTTP application.
The server only has to return a `TaskId` in the handler creating the long
running task.
"""

from ._manager import get_long_running_manager
from ._server import setup, start_long_running_task

__all__: tuple[str, ...] = (
    "get_long_running_manager",
    "setup",
    "start_long_running_task",
)

# nopycln: file
