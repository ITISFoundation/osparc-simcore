"""
Provides a convenient way to return the result given a TaskId.
"""

from ._client import BaseClient, HttpClient, RPCClient, setup
from ._context_manager import periodic_task_result  # attach to the same object!

__all__: tuple[str, ...] = (
    "BaseClient",
    "HttpClient",
    "periodic_task_result",
    "RPCClient",
    "setup",
)
# nopycln: file
