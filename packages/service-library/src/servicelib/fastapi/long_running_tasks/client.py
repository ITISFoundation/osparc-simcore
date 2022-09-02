"""
Provides a convenient way to return the result given a TaskId.
"""

from ...long_running_tasks._errors import TaskClientResultError
from ...long_running_tasks._models import (
    ClientConfiguration,
    ProgressCallback,
    ProgressMessage,
    ProgressPercent,
)
from ...long_running_tasks._task import TaskId, TaskResult
from ._client import DEFAULT_HTTP_REQUESTS_TIMEOUT, Client, setup
from ._context_manager import periodic_task_result

__all__: tuple[str, ...] = (
    "Client",
    "ClientConfiguration",
    "DEFAULT_HTTP_REQUESTS_TIMEOUT",
    "periodic_task_result",
    "ProgressCallback",
    "ProgressMessage",
    "ProgressPercent",
    "setup",
    "TaskClientResultError",
    "TaskId",
    "TaskResult",
)
