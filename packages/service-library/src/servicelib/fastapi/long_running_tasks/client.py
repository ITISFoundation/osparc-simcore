"""
Provides a convenient way to return the result given a TaskId.
"""

import logging

from ._client import Client, setup
from ._context_manager import periodic_task_result

_logger = logging.getLogger(__name__)


__all__: tuple[str, ...] = (
    "Client",
    "periodic_task_result",
    "setup",
)
# nopycln: file
