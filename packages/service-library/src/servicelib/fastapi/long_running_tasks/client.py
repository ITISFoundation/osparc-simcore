"""
Provides a convenient way to return the result given a TaskId.
"""

from ._client import setup
from ._context_manager import task_result
from ._models import TaskId

__all__: tuple[str, ...] = (
    "setup",
    "task_result",
    "TaskId",
)
