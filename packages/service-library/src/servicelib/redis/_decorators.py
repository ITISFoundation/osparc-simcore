import asyncio
import functools
import logging
import socket
from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any, Final, ParamSpec, TypeVar

import arrow
import redis.exceptions
from redis.asyncio.lock import Lock
from servicelib.logging_errors import create_troubleshootting_log_kwargs

from ..background_task import periodic
from ._client import RedisClientSDK
from ._constants import DEFAULT_LOCK_TTL
from ._errors import CouldNotAcquireLockError, LockLostError
from ._utils import auto_extend_lock

_logger = logging.getLogger(__file__)

P = ParamSpec("P")
R = TypeVar("R")

_EXCLUSIVE_TASK_NAME: Final[str] = "exclusive/{module_name}.{func_name}"
_EXCLUSIVE_AUTO_EXTEND_TASK_NAME: Final[str] = (
    "exclusive/autoextend_lock_{redis_lock_key}"
)


@periodic(interval=DEFAULT_LOCK_TTL / 2, raise_on_error=True)
async def _periodic_auto_extender(lock: Lock, started_event: asyncio.Event) -> None:
    await auto_extend_lock(lock)
    started_event.set()


def exclusive(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    lock_key: str | Callable[..., str],
    lock_value: bytes | str | None = None,
    blocking: bool = False,
    blocking_timeout: timedelta | None = None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    """
    Define a method to run exclusively across
    processes by leveraging a Redis Lock.

    Arguments:
        redis -- the redis client
        lock_key -- a string as the name of the lock (good practice: app_name:lock_name)
        lock_value -- some additional data that can be retrieved by another client if None,
                    it will be automatically filled with the current time and the client name

    Raises:
        - ValueError if used incorrectly
        - CouldNotAcquireLockError if the lock could not be acquired
        - LockLostError if the lock was lost (e.g. due to Redis restart, or TTL was not extended in time)
    """

    if not lock_key:
        msg = "lock_key cannot be empty string!"
        raise ValueError(msg)

    def _decorator(
        coro: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(coro)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
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
            nonlocal lock_value
            if lock_value is None:
                lock_value = f"locked since {arrow.utcnow().format()} by {client.client_name} on {socket.gethostname()}"

            lock = client.create_lock(redis_lock_key, ttl=DEFAULT_LOCK_TTL)
            if not await lock.acquire(
                token=lock_value,
                blocking=blocking,
                blocking_timeout=(
                    blocking_timeout.total_seconds() if blocking_timeout else None
                ),
            ):
                raise CouldNotAcquireLockError(lock=lock)

            try:
                async with asyncio.TaskGroup() as tg:
                    started_event = asyncio.Event()
                    # first create a task that will auto-extend the lock
                    auto_extend_lock_task = tg.create_task(
                        _periodic_auto_extender(lock, started_event),
                        name=_EXCLUSIVE_AUTO_EXTEND_TASK_NAME.format(
                            redis_lock_key=redis_lock_key
                        ),
                    )
                    # NOTE: In case the work thread is raising right away,
                    # this ensures the extend task ran once and ensure cancellation works
                    await started_event.wait()

                    # then the task that runs the user code
                    assert asyncio.iscoroutinefunction(coro)  # nosec
                    work_task = tg.create_task(
                        coro(*args, **kwargs),
                        name=_EXCLUSIVE_TASK_NAME.format(
                            module_name=coro.__module__, func_name=coro.__name__
                        ),
                    )

                    res = await work_task
                    auto_extend_lock_task.cancel()
                    return res

            except BaseExceptionGroup as eg:
                # Separate exceptions into LockLostError and others
                lock_lost_errors, other_errors = eg.split(LockLostError)

                # If there are any other errors, re-raise them
                if other_errors:
                    assert len(other_errors.exceptions) == 1  # nosec
                    raise other_errors.exceptions[0] from eg

                assert lock_lost_errors is not None  # nosec
                assert len(lock_lost_errors.exceptions) == 1  # nosec
                raise lock_lost_errors.exceptions[0] from eg
            finally:
                try:
                    # in the case where the lock would have been lost,
                    # this would raise again and is not necessary
                    await lock.release()
                except redis.exceptions.LockNotOwnedError as exc:
                    _logger.exception(
                        **create_troubleshootting_log_kwargs(
                            f"Unexpected error while releasing lock '{redis_lock_key}'",
                            error=exc,
                            error_context={
                                "redis_lock_key": redis_lock_key,
                                "lock_value": lock_value,
                                "client_name": client.client_name,
                                "hostname": socket.gethostname(),
                                "coroutine": coro.__name__,
                            },
                            tip="This might happen if the lock was lost before releasing it. "
                            "Look for synchronous code that prevents refreshing the lock or asyncio loop overload.",
                        )
                    )

        return _wrapper

    return _decorator
