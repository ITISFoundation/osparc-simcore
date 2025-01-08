import contextlib
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

import redis.exceptions

from ..background_task import periodic_task
from ._client import RedisClientSDK
from ._constants import DEFAULT_LOCK_TTL
from ._errors import CouldNotAcquireLockError
from ._utils import auto_extend_lock

_logger = logging.getLogger(__file__)

P = ParamSpec("P")
R = TypeVar("R")


def exclusive(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    lock_key: str | Callable[..., str],
    lock_value: bytes | str | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Define a method to run exclusively across
    processes by leveraging a Redis Lock.

    parameters:
    redis: the redis client SDK
    lock_key: a string as the name of the lock (good practice: app_name:lock_name)
    lock_value: some additional data that can be retrieved by another client

    Raises:
        - ValueError if used incorrectly
        - CouldNotAcquireLockError if the lock could not be acquired
    """

    if not lock_key:
        msg = "lock_key cannot be empty string!"
        raise ValueError(msg)

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            redis_lock_key = (
                lock_key(*args, **kwargs) if callable(lock_key) else lock_key
            )
            assert isinstance(redis_lock_key, str)  # nosec

            client = (
                redis_client(*args, **kwargs)
                if callable(redis_client)
                else redis_client
            )
            assert isinstance(redis_client, RedisClientSDK)  # nosec

            lock_ttl = DEFAULT_LOCK_TTL

            lock = client.create_lock(redis_lock_key, ttl=lock_ttl)
            if not await lock.acquire(token=lock_value):
                raise CouldNotAcquireLockError(lock=lock)

            try:
                async with periodic_task(
                    auto_extend_lock,
                    interval=lock_ttl / 2,
                    task_name=f"autoextend_lock_{redis_lock_key}",
                    lock=lock,
                ) as auto_extend_task:
                    result = await func(*args, **kwargs)
                return result
            finally:
                with contextlib.suppress(redis.exceptions.LockNotOwnedError):
                    # in the case where the lock would have been lost, this would raise
                    await lock.release()

            async with redis_client.lock_context(
                lock_key=redis_lock_key, lock_value=lock_value
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
