import logging
from collections.abc import Awaitable
from typing import Any

import redis.exceptions
from redis.asyncio.lock import Lock

from ..logging_utils import log_context
from ._errors import LockLostError

_logger = logging.getLogger(__name__)


async def auto_extend_lock(lock: Lock) -> None:
    """automatically extend a distributed lock TTL (time to live) by re-acquiring the lock

    Arguments:
        lock -- the lock to auto-extend

    Raises:
        LockLostError: in case the lock is not available anymore
        LockError: in case of wrong usage (no timeout or lock was not previously acquired)
    """
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
