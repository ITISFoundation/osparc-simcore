import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, ParamSpec, TypeVar

import arrow

from .background_task import start_periodic_task
from .redis import CouldNotAcquireLockError, RedisClientSDK

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


async def _exclusive_task_starter(
    redis: RedisClientSDK,
    usr_tsk_task: Callable[..., Awaitable[None]],
    *,
    usr_tsk_interval: timedelta,
    usr_tsk_task_name: str,
    **kwargs,
) -> None:
    lock_key = f"lock:exclusive_task_starter:{usr_tsk_task_name}"
    lock_value = f"locked since {arrow.utcnow().format()}"

    try:
        await exclusive(redis, lock_key=lock_key, lock_value=lock_value)(
            start_periodic_task
        )(
            usr_tsk_task,
            interval=usr_tsk_interval,
            task_name=usr_tsk_task_name,
            **kwargs,
        )
    except CouldNotAcquireLockError:
        _logger.debug(
            "Could not acquire lock '%s' with value '%s'", lock_key, lock_value
        )
    except Exception as e:
        _logger.exception(e)  # noqa: TRY401
        raise


def start_exclusive_periodic_task(
    redis: RedisClientSDK,
    task: Callable[..., Awaitable[None]],
    *,
    task_period: timedelta,
    retry_after: timedelta = timedelta(seconds=1),
    task_name: str,
    **kwargs,
) -> asyncio.Task:
    """
    Ensures that only 1 process periodically ever runs ``task`` at all times.
    If one process dies, another process will run the ``task``.

    Creates a background task that periodically tries to start the user ``task``.
    Before the ``task`` is scheduled for periodic background execution, it acquires a lock.
    Subsequent calls to ``start_exclusive_periodic_task`` will not allow the same ``task``
    to start since the lock will prevent the scheduling.

    Q&A:
    - Why is `_exclusive_task_starter` run as a task?
        This is usually used at setup time and cannot block the setup process forever
    - Why is `_exclusive_task_starter` task a periodic task?
        If Redis connectivity is lost, the periodic `_exclusive_task_starter` ensures the lock is
        reacquired
    """
    return start_periodic_task(
        _exclusive_task_starter,
        interval=retry_after,
        task_name=f"exclusive_task_starter_{task_name}",
        redis=redis,
        usr_tsk_task=task,
        usr_tsk_interval=task_period,
        usr_tsk_task_name=task_name,
        **kwargs,
    )


async def handle_redis_returns_union_types(result: Any | Awaitable[Any]) -> Any:
    """Used to handle mypy issues with redis 5.x return types"""
    if isinstance(result, Awaitable):
        return await result
    return result
