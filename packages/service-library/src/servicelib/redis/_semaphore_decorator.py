import datetime
import functools
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, ParamSpec, TypeVar

from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
    DEFAULT_SEMAPHORE_TTL,
)
from ._semaphore import distributed_semaphore

_logger = logging.getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


def with_limited_concurrency(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    key: str | Callable[..., str],
    capacity: int | Callable[..., int],
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    blocking: bool = True,
    blocking_timeout: datetime.timedelta | None = None,
    expected_lock_overall_time: datetime.timedelta = DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
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
            semaphore_key = key(*args, **kwargs) if callable(key) else key
            semaphore_capacity = capacity(*args, **kwargs) if callable(capacity) else capacity
            client = redis_client(*args, **kwargs) if callable(redis_client) else redis_client

            assert isinstance(semaphore_key, str)  # nosec
            assert isinstance(semaphore_capacity, int)  # nosec
            assert isinstance(client, RedisClientSDK)  # nosec

            async with distributed_semaphore(
                redis_client=client,
                key=semaphore_key,
                capacity=semaphore_capacity,
                ttl=ttl,
                blocking=blocking,
                blocking_timeout=blocking_timeout,
                expected_lock_overall_time=expected_lock_overall_time,
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
    blocking_timeout: datetime.timedelta | None = None,
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
            semaphore_key = key(*args, **kwargs) if callable(key) else key
            semaphore_capacity = capacity(*args, **kwargs) if callable(capacity) else capacity
            client = redis_client(*args, **kwargs) if callable(redis_client) else redis_client

            assert isinstance(semaphore_key, str)  # nosec
            assert isinstance(semaphore_capacity, int)  # nosec
            assert isinstance(client, RedisClientSDK)  # nosec

            async with (
                distributed_semaphore(
                    redis_client=client,
                    key=semaphore_key,
                    capacity=semaphore_capacity,
                    ttl=ttl,
                    blocking=blocking,
                    blocking_timeout=blocking_timeout,
                    expected_lock_overall_time=expected_lock_overall_time,
                ),
                cm_func(*args, **kwargs) as value,
            ):
                yield value

        return _wrapper

    return _decorator
