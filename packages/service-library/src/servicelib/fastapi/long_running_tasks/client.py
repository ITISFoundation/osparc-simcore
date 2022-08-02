"""
Provides a convenient way to return the result given a TaskId.
"""

from ._client import Client, setup
from ._context_manager import periodic_task_result, periodic_tasks_results
from ._errors import TaskClientResultError
from ._models import CancelResult, ProgressMessage, ProgressPercent, TaskId, TaskResult

__all__: tuple[str, ...] = (
    "CancelResult",
    "Client",
    "periodic_task_result",
    "periodic_tasks_results",
    "ProgressMessage",
    "ProgressPercent",
    "setup",
    "TaskClientResultError",
    "TaskId",
    "TaskResult",
)
