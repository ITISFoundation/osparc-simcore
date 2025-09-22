import asyncio
import datetime
import functools
import logging
import socket
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, ParamSpec, TypeVar

import arrow
from common_library.async_tools import cancel_wait_task
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs

from ..background_task import periodic
from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
    DEFAULT_SEMAPHORE_TTL,
    DEFAULT_SOCKET_TIMEOUT,
)
from ._errors import (
    SemaphoreAcquisitionError,
    SemaphoreLostError,
    SemaphoreNotAcquiredError,
)
from ._semaphore import DistributedSemaphore

_logger = logging.getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


@asynccontextmanager
async def _managed_semaphore_execution(
    semaphore: DistributedSemaphore,
    semaphore_key: str,
    ttl: datetime.timedelta,
    execution_context: str,
    expected_lock_overall_time: datetime.timedelta,
) -> AsyncIterator:
    """Common semaphore management logic with auto-renewal."""
    # Acquire the semaphore first
    if not await semaphore.acquire():
        raise SemaphoreAcquisitionError(name=semaphore_key, capacity=semaphore.capacity)

    lock_acquisition_time = arrow.utcnow()
    try:
        # NOTE: Use TaskGroup for proper exception propagation, this ensures that in case of error the context manager will be properly exited
        # and the semaphore released.
        # If we use create_task() directly, exceptions in the task are not propagated to the parent task
        # and the context manager may never exit, leading to semaphore leaks.
        async with asyncio.TaskGroup() as tg:
            started_event = asyncio.Event()

            # Create auto-renewal task
            @periodic(interval=ttl / 3, raise_on_error=True)
            async def _periodic_renewer() -> None:
                await semaphore.reacquire()
                if not started_event.is_set():
                    started_event.set()

            # Start the renewal task
            renewal_task = tg.create_task(
                _periodic_renewer(),
                name=f"semaphore/autorenewal_{semaphore_key}_{semaphore.instance_id}",
            )
            await started_event.wait()

            yield

            # NOTE: if we do not explicitely await the task inside the context manager
            # it sometimes hangs forever (Python issue?)
            await cancel_wait_task(renewal_task, max_delay=None)

    except BaseExceptionGroup as eg:
        semaphore_lost_errors, other_errors = eg.split(SemaphoreLostError)
        # If there are any other errors, re-raise them
        if other_errors:
            assert len(other_errors.exceptions) == 1  # nosec
            raise other_errors.exceptions[0] from eg

        assert semaphore_lost_errors is not None  # nosec
        assert len(semaphore_lost_errors.exceptions) == 1  # nosec
        raise semaphore_lost_errors.exceptions[0] from eg

    finally:
        # Always attempt to release the semaphore
        try:
            await semaphore.release()
        except SemaphoreNotAcquiredError as exc:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Unexpected error while releasing semaphore '{semaphore_key}'",
                    error=exc,
                    error_context={
                        "semaphore_key": semaphore_key,
                        "client_name": semaphore.redis_client.client_name,
                        "hostname": socket.gethostname(),
                        "execution_context": execution_context,
                    },
                    tip="This might happen if the semaphore was lost before releasing it. "
                    "Look for synchronous code that prevents refreshing the semaphore or asyncio loop overload.",
                )
            )
        finally:
            lock_release_time = arrow.utcnow()
            locking_time = lock_release_time - lock_acquisition_time
            if locking_time > expected_lock_overall_time:
                _logger.warning(
                    "Semaphore '%s' was held for %s which is longer than expected (%s). "
                    "TIP: consider reducing the locking time by optimizing the code inside "
                    "the critical section or increasing the default locking time",
                    semaphore_key,
                    locking_time,
                    expected_lock_overall_time,
                )


def _create_semaphore(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    args: tuple[Any, ...],
    *,
    key: str | Callable[..., str],
    capacity: int | Callable[..., int],
    ttl: datetime.timedelta,
    blocking: bool,
    blocking_timeout: datetime.timedelta | None,
    kwargs: dict[str, Any],
) -> tuple[DistributedSemaphore, str]:
    """Create and configure a distributed semaphore from callable or static parameters."""
    semaphore_key = key(*args, **kwargs) if callable(key) else key
    semaphore_capacity = capacity(*args, **kwargs) if callable(capacity) else capacity
    client = redis_client(*args, **kwargs) if callable(redis_client) else redis_client

    assert isinstance(semaphore_key, str)  # nosec
    assert isinstance(semaphore_capacity, int)  # nosec
    assert isinstance(client, RedisClientSDK)  # nosec

    semaphore = DistributedSemaphore(
        redis_client=client,
        key=semaphore_key,
        capacity=semaphore_capacity,
        ttl=ttl,
        blocking=blocking,
        blocking_timeout=blocking_timeout,
    )

    return semaphore, semaphore_key


def with_limited_concurrency(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    key: str | Callable[..., str],
    capacity: int | Callable[..., int],
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    blocking: bool = True,
    blocking_timeout: datetime.timedelta | None = DEFAULT_SOCKET_TIMEOUT,
    expected_lock_overall_time: datetime.timedelta = DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    """
    Decorator to limit concurrent execution of a function using a distributed semaphore.

    This decorator ensures that only a specified number of instances of the decorated
    function can run concurrently across multiple processes/instances using Redis
    as the coordination backend.

    Args:
        redis_client: Redis client for coordination (can be callable)
        key: Unique identifier for the semaphore (can be callable)
        capacity: Maximum number of concurrent executions (can be callable)
        ttl: Time-to-live for semaphore entries (default: 5 minutes)
        blocking: Whether to block when semaphore is full (default: True)
        blocking_timeout: Maximum time to wait when blocking (default: socket timeout)
        expected_lock_overall_time: helper for logging warnings if lock is held longer than expected

    Example:
        @with_limited_concurrency(
            redis_client,
            key=f"{user_id}-{wallet_id}",
            capacity=20,
            blocking=True,
            blocking_timeout=None
        )
        async def process_user_wallet(user_id: str, wallet_id: str):
            # Only 20 instances of this function can run concurrently
            # for the same user_id-wallet_id combination
            await do_processing()

    Raises:
        SemaphoreAcquisitionError: If semaphore cannot be acquired and blocking=True
    """

    def _decorator(
        coro: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(coro)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            semaphore, semaphore_key = _create_semaphore(
                redis_client,
                args,
                key=key,
                capacity=capacity,
                ttl=ttl,
                blocking=blocking,
                blocking_timeout=blocking_timeout,
                kwargs=kwargs,
            )

            async with _managed_semaphore_execution(
                semaphore,
                semaphore_key,
                ttl,
                f"coroutine_{coro.__name__}",
                expected_lock_overall_time,
            ):
                return await coro(*args, **kwargs)

        return _wrapper

    return _decorator


def with_limited_concurrency_cm(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    key: str | Callable[..., str],
    capacity: int | Callable[..., int],
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    blocking: bool = True,
    blocking_timeout: datetime.timedelta | None = DEFAULT_SOCKET_TIMEOUT,
    expected_lock_overall_time: datetime.timedelta = DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
) -> Callable[
    [Callable[P, AbstractAsyncContextManager[R]]],
    Callable[P, AbstractAsyncContextManager[R]],
]:
    """
    Decorator to limit concurrent execution of async context managers using a distributed semaphore.

    This decorator ensures that only a specified number of instances of the decorated
    async context manager can be active concurrently across multiple processes/instances
    using Redis as the coordination backend.

    Args:
        redis_client: Redis client for coordination (can be callable)
        key: Unique identifier for the semaphore (can be callable)
        capacity: Maximum number of concurrent executions (can be callable)
        ttl: Time-to-live for semaphore entries (default: 5 minutes)
        blocking: Whether to block when semaphore is full (default: True)
        blocking_timeout: Maximum time to wait when blocking (default: socket timeout)
        expected_lock_overall_time: helper for logging warnings if lock is held longer than expected

    Example:
        @asynccontextmanager
        @with_limited_concurrency_cm(
            redis_client,
            key="cluster:my-cluster",
            capacity=5,
            blocking=True,
            blocking_timeout=None
        )
        async def get_cluster_client():
            async with pool.acquire() as client:
                yield client

    Raises:
        SemaphoreAcquisitionError: If semaphore cannot be acquired and blocking=True
    """

    def _decorator(
        cm_func: Callable[P, AbstractAsyncContextManager[R]],
    ) -> Callable[P, AbstractAsyncContextManager[R]]:
        @functools.wraps(cm_func)
        @asynccontextmanager
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncIterator[R]:
            semaphore, semaphore_key = _create_semaphore(
                redis_client,
                args,
                key=key,
                capacity=capacity,
                ttl=ttl,
                blocking=blocking,
                blocking_timeout=blocking_timeout,
                kwargs=kwargs,
            )

            async with (
                _managed_semaphore_execution(
                    semaphore,
                    semaphore_key,
                    ttl,
                    f"context_manager_{cm_func.__name__}",
                    expected_lock_overall_time,
                ),
                cm_func(*args, **kwargs) as value,
            ):
                yield value

        return _wrapper

    return _decorator
