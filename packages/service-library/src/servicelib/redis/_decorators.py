import asyncio
import contextlib
import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

import redis.exceptions

from ..background_task import periodic_task
from ..logging_utils import log_context
from ._client import RedisClientSDK
from ._constants import DEFAULT_LOCK_TTL, SHUTDOWN_TIMEOUT_S
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
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    """
        Define a method to run exclusively across
        processes by leveraging a Redis Lock.
    a1f69fdefa14fae2fee03fac7e89f27e44b13aa9
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

    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
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
            assert isinstance(client, RedisClientSDK)  # nosec

            lock = client.create_lock(redis_lock_key, ttl=DEFAULT_LOCK_TTL)
            if not await lock.acquire(token=lock_value):
                raise CouldNotAcquireLockError(lock=lock)

            try:
                async with periodic_task(
                    auto_extend_lock,
                    interval=DEFAULT_LOCK_TTL / 2,
                    task_name=f"autoextend_exclusive_lock_{redis_lock_key}",
                    raise_on_error=True,
                    lock=lock,
                ) as auto_extend_task:
                    assert asyncio.iscoroutinefunction(func)  # nosec
                    work_task = asyncio.create_task(
                        func(*args, **kwargs), name=f"exclusive_{func.__name__}"
                    )
                    done, _pending = await asyncio.wait(
                        [work_task, auto_extend_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    # the task finished, let's return its result whatever it is
                    if work_task in done:
                        return await work_task

                    # the auto extend task can only finish if it raised an error, so it's bad
                    _logger.error(
                        "lock %s could not be auto-extended, cancelling work task! "
                        "TIP: check connection to Redis DBs or look for Synchronous "
                        "code that might block the auto-extender task.",
                        lock.name,
                    )
                    with log_context(_logger, logging.DEBUG, msg="cancel work task"):
                        work_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                            # this will raise any other error that could have happened in the work task
                            await asyncio.wait_for(
                                work_task, timeout=SHUTDOWN_TIMEOUT_S
                            )
                    # return the extend task raised error
                    return await auto_extend_task

            finally:
                with contextlib.suppress(redis.exceptions.LockNotOwnedError):
                    # in the case where the lock would have been lost,
                    # this would raise again and is not necessary
                    await lock.release()

        return wrapper

    return decorator
