import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from ._client import RedisClientSDK

_logger = logging.getLogger(__file__)

P = ParamSpec("P")
R = TypeVar("R")


def exclusive(
    redis: RedisClientSDK | Callable[..., RedisClientSDK],
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

            redis_client = redis(*args, **kwargs) if callable(redis) else redis
            assert isinstance(redis_client, RedisClientSDK)  # nosec

            async with redis_client.lock_context(
                lock_key=redis_lock_key, lock_value=lock_value
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
