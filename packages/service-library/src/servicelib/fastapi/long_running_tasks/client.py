"""
Provides a convenient way to return the result given a TaskId.
"""

from ...long_running_tasks._errors import TaskClientResultError
from ...long_running_tasks._models import (
    CancelResult,
    ProgressCallback,
    ProgressMessage,
    ProgressPercent,
)
from ...long_running_tasks._task import TaskId, TaskResult
from ._client import Client, setup
from ._context_manager import periodic_task_result

__all__: tuple[str, ...] = (
    "CancelResult",
    "Client",
    "periodic_task_result",
    "ProgressCallback",
    "ProgressMessage",
    "ProgressPercent",
    "setup",
    "TaskClientResultError",
    "TaskId",
    "TaskResult",
)
