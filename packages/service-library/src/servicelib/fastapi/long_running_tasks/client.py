"""
Provides a convenient way to return the result given a TaskId.
"""

from ._client import setup, Client
from ._context_manager import periodic_task_result
from ._models import TaskId, TaskResult, CancelResult
from ._errors import TaskClientResultError

__all__: tuple[str, ...] = (
    "CancelResult",
    "Client",
    "periodic_task_result",
    "setup",
    "TaskClientResultError",
    "TaskId",
    "TaskResult",
)
