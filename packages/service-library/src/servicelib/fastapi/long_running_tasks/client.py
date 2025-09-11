"""
Provides a convenient way to return the result given a TaskId.
"""

from ._client import HttpClient, setup
from ._context_manager import periodic_task_result  # attach to the same object!

__all__: tuple[str, ...] = (
    "HttpClient",
    "periodic_task_result",
    "setup",
)
# nopycln: file
