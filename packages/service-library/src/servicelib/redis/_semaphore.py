import asyncio
import datetime
import functools
import logging
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, ParamSpec, TypeVar

from common_library.async_tools import cancel_wait_task

from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_SEMAPHORE_TTL,
    DEFAULT_SOCKET_TIMEOUT,
    SEMAPHORE_HOLDER_KEY_PREFIX,
    SEMAPHORE_KEY_PREFIX,
)
from ._errors import BaseRedisError

_logger = logging.getLogger(__name__)


class SemaphoreAcquisitionError(BaseRedisError):
    """Raised when semaphore cannot be acquired"""

    msg_template: str = "Could not acquire semaphore '{name}' (capacity: {capacity})"


class SemaphoreNotAcquiredError(BaseRedisError):
    """Raised when trying to release a semaphore that was not acquired"""

    msg_template: str = "Semaphore '{name}' was not acquired by this instance"


class DistributedRedSemaphore:
    """
    A distributed semaphore implementation using Redis.

    This semaphore allows limiting the number of concurrent operations across
    multiple processes/instances using Redis as the coordination backend.

    Args:
        redis_client: Redis client for coordination
        name: Unique identifier for the semaphore
        capacity: Maximum number of concurrent holders
        ttl: Time-to-live for semaphore entries (auto-cleanup)
        blocking: Whether acquire() should block until available
        timeout: Maximum time to wait when blocking (None = no timeout)

    Example:
        async with DistributedRedSemaphore(
            redis_client, "my_resource", capacity=3
        ):
            # Only 3 instances can execute this block concurrently
            await do_limited_work()
    """

    def __init__(
        self,
        redis_client: RedisClientSDK,
        key: str,
        capacity: int,
        *,
        ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
        blocking: bool = True,
        timeout: datetime.timedelta | None = DEFAULT_SOCKET_TIMEOUT,
    ) -> None:
        if capacity <= 0:
            msg = f"Semaphore capacity must be positive, got {capacity}"
            raise ValueError(msg)

        self._redis_client = redis_client
        self._key = key
        self._capacity = capacity
        self._ttl = ttl
        self._blocking = blocking
        self._timeout = timeout

        # Unique identifier for this semaphore instance
        self._instance_id = str(uuid.uuid4())

        # Redis keys
        self._semaphore_key = f"{SEMAPHORE_KEY_PREFIX}{key}"
        self._holder_key = f"{SEMAPHORE_HOLDER_KEY_PREFIX}{key}:{self._instance_id}"

        # State tracking
        self._acquired = False
        self._auto_renew_task: asyncio.Task[None] | None = None

    async def acquire(self) -> bool:
        """
        Acquire the semaphore.

        Returns:
            True if acquired successfully, False if not acquired and non-blocking

        Raises:
            SemaphoreAcquisitionError: If acquisition fails and blocking=True
        """
        if self._acquired:
            return True

        start_time = asyncio.get_event_loop().time()
        timeout_seconds = self._timeout.total_seconds() if self._timeout else None

        while True:
            # Try to acquire using Redis sorted set for atomic operations
            acquired = await self._try_acquire()

            if acquired:
                self._acquired = True
                # Start auto-renewal task
                await self._start_auto_renew()
                _logger.debug(
                    "Acquired semaphore '%s' (instance: %s)",
                    self._key,
                    self._instance_id,
                )
                return True

            if not self._blocking:
                return False

            # Check timeout
            if timeout_seconds is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout_seconds:
                    if self._blocking:
                        raise SemaphoreAcquisitionError(
                            name=self._key, capacity=self._capacity
                        )
                    return False

            # Wait a bit before retrying
            await asyncio.sleep(0.1)

    async def release(self) -> None:
        """
        Release the semaphore.

        Raises:
            SemaphoreNotAcquiredError: If semaphore was not acquired by this instance
        """
        if not self._acquired:
            raise SemaphoreNotAcquiredError(name=self._key)

        # Stop auto-renewal
        if self._auto_renew_task:
            await cancel_wait_task(self._auto_renew_task)
            self._auto_renew_task = None

        # Remove from Redis
        async with self._redis_client.redis.pipeline(transaction=True) as pipe:
            await pipe.zrem(self._semaphore_key, self._instance_id)
            await pipe.delete(self._holder_key)
            await pipe.execute()

        self._acquired = False
        _logger.debug(
            "Released semaphore '%s' (instance: %s)",
            self._key,
            self._instance_id,
        )

    async def _try_acquire(self) -> bool:
        """Atomically try to acquire the semaphore using Redis operations"""
        current_time = asyncio.get_event_loop().time()
        ttl_seconds = self._ttl.total_seconds()

        try:
            # Clean up expired entries first
            await self._redis_client.redis.zremrangebyscore(
                self._semaphore_key, "-inf", current_time - ttl_seconds
            )

            # Use Redis transactions for atomic operations
            async with self._redis_client.redis.pipeline(transaction=True) as pipe:
                # Watch the semaphore key for changes
                await pipe.watch(self._semaphore_key)

                # Check current count
                current_count = await self._redis_client.redis.zcard(
                    self._semaphore_key
                )

                if current_count < self._capacity:
                    # Try to acquire
                    pipe.multi()
                    pipe.zadd(self._semaphore_key, {self._instance_id: current_time})
                    pipe.setex(self._holder_key, int(ttl_seconds), "1")
                    result = await pipe.execute()
                    return bool(result)

                # Cancel the transaction
                await pipe.reset()
                return False

        except Exception:
            _logger.exception(
                "Failed to acquire semaphore '%s'",
                self._key,
            )
            return False

    async def _start_auto_renew(self) -> None:
        """Start the auto-renewal task to prevent TTL expiration"""
        if self._auto_renew_task:
            return

        async def _renew_periodically() -> None:
            # Renew at 1/3 of TTL interval to be safe
            renew_interval = self._ttl.total_seconds() / 3

            while self._acquired:
                try:
                    await asyncio.sleep(renew_interval)
                    if not self._acquired:
                        break

                    current_time = asyncio.get_event_loop().time()
                    ttl_seconds = self._ttl.total_seconds()

                    # Update timestamp in sorted set and refresh holder key
                    async with self._redis_client.redis.pipeline(
                        transaction=True
                    ) as pipe:
                        await pipe.zadd(
                            self._semaphore_key, {self._instance_id: current_time}
                        )
                        await pipe.expire(self._holder_key, int(ttl_seconds))
                        await pipe.execute()

                except asyncio.CancelledError:
                    break
                except Exception:
                    _logger.warning(
                        "Failed to renew semaphore '%s'",
                        self._key,
                    )

        self._auto_renew_task = asyncio.create_task(_renew_periodically())

    async def get_current_count(self) -> int:
        """Get the current number of semaphore holders"""
        current_time = asyncio.get_event_loop().time()
        ttl_seconds = self._ttl.total_seconds()

        # Remove expired entries and count remaining
        async with self._redis_client.redis.pipeline(transaction=True) as pipe:
            await pipe.zremrangebyscore(
                self._semaphore_key, "-inf", current_time - ttl_seconds
            )
            await pipe.zcard(self._semaphore_key)
            results = await pipe.execute()

        return int(results[1])

    async def get_available_count(self) -> int:
        """Get the number of available semaphore slots"""
        current_count = await self.get_current_count()
        return max(0, self._capacity - current_count)

    # Context manager support
    async def __aenter__(self) -> "DistributedRedSemaphore":
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._acquired:
            await self.release()

    def __repr__(self) -> str:
        return (
            f"DistributedRedSemaphore(name={self._key!r}, "
            f"capacity={self._capacity}, acquired={self._acquired})"
        )


P = ParamSpec("P")
R = TypeVar("R")


def with_limited_concurrency(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    key: str | Callable[..., str],
    capacity: int | Callable[..., int],
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    blocking: bool = True,
    blocking_timeout: datetime.timedelta | None = DEFAULT_SOCKET_TIMEOUT,
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
            # Resolve callable parameters
            semaphore_key = key(*args, **kwargs) if callable(key) else key
            semaphore_capacity = (
                capacity(*args, **kwargs) if callable(capacity) else capacity
            )
            client = (
                redis_client(*args, **kwargs)
                if callable(redis_client)
                else redis_client
            )

            assert isinstance(semaphore_key, str)  # nosec
            assert isinstance(semaphore_capacity, int)  # nosec
            assert isinstance(client, RedisClientSDK)  # nosec

            # Create and use the semaphore
            semaphore = DistributedRedSemaphore(
                redis_client=client,
                key=semaphore_key,
                capacity=semaphore_capacity,
                ttl=ttl,
                blocking=blocking,
                timeout=blocking_timeout,
            )

            async with semaphore:
                return await coro(*args, **kwargs)

        return _wrapper

    return _decorator


@asynccontextmanager
async def distributed_semaphore(
    redis_client: RedisClientSDK,
    name: str,
    capacity: int,
    **kwargs: Any,
) -> AsyncIterator[DistributedRedSemaphore]:
    """
    Async context manager for distributed semaphore.

    Args:
        redis_client: Redis client for coordination
        name: Unique identifier for the semaphore
        capacity: Maximum number of concurrent holders
        **kwargs: Additional arguments for DistributedRedSemaphore

    Example:
        async with distributed_semaphore(
            redis_client, "my_resource", capacity=3
        ) as sem:
            print(f"Available slots: {await sem.get_available_count()}")
            await do_limited_work()
    """
    semaphore = DistributedRedSemaphore(redis_client, name, capacity, **kwargs)
    async with semaphore:
        yield semaphore
