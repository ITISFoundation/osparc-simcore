import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

import redis.exceptions
from redis.asyncio.lock import Lock

from ..logging_utils import log_context
from ._constants import SHUTDOWN_TIMEOUT_S
from ._errors import LockLostError

_logger = logging.getLogger(__name__)


async def cancel_or_warn(task: asyncio.Task) -> None:
    if not task.cancelled():
        task.cancel()
    _, pending = await asyncio.wait((task,), timeout=SHUTDOWN_TIMEOUT_S)
    if pending:
        task_name = task.get_name()
        _logger.warning("Could not cancel task_name=%s pending=%s", task_name, pending)


async def auto_extend_lock(lock: Lock) -> None:
    try:
        with log_context(_logger, logging.DEBUG, f"Autoextend lock {lock.name!r}"):
            await lock.reacquire()
    except redis.exceptions.LockNotOwnedError as exc:
        raise LockLostError(lock=lock) from exc


async def handle_redis_returns_union_types(result: Any | Awaitable[Any]) -> Any:
    """Used to handle mypy issues with redis 5.x return types"""
    if isinstance(result, Awaitable):
        return await result
    return result
