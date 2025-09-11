import asyncio
import datetime
import functools
import logging
import uuid
from collections.abc import Callable, Coroutine
from types import TracebackType
from typing import Annotated, Any, ParamSpec, TypeVar

from common_library.async_tools import cancel_wait_task
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    PrivateAttr,
    computed_field,
    field_validator,
)

from ..background_task import periodic
from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_SEMAPHORE_TTL,
    DEFAULT_SOCKET_TIMEOUT,
    SEMAPHORE_HOLDER_KEY_PREFIX,
    SEMAPHORE_KEY_PREFIX,
)
from ._errors import SemaphoreAcquisitionError, SemaphoreNotAcquiredError

_logger = logging.getLogger(__name__)


class DistributedSemaphore(BaseModel):
    """
    A distributed semaphore implementation using Redis.

    This semaphore allows limiting the number of concurrent operations across
    multiple processes/instances using Redis as the coordination backend.

    Args:
        redis_client: Redis client for coordination
        key: Unique identifier for the semaphore
        capacity: Maximum number of concurrent holders
        ttl: Time-to-live for semaphore entries (auto-cleanup)
        blocking: Whether acquire() should block until available
        timeout: Maximum time to wait when blocking (None = no timeout)

    Example:
        async with DistributedSemaphore(
            redis_client, "my_resource", capacity=3
        ):
            # Only 3 instances can execute this block concurrently
            await do_limited_work()
    """

    # Model configuration
    model_config = {
        "arbitrary_types_allowed": True,  # For RedisClientSDK
        "validate_assignment": True,  # Validate on field assignment
        "extra": "forbid",  # Prevent extra fields
    }

    # Configuration fields with validation
    redis_client: RedisClientSDK
    key: Annotated[
        str, Field(min_length=1, description="Unique identifier for the semaphore")
    ]
    capacity: Annotated[
        PositiveInt, Field(description="Maximum number of concurrent holders")
    ]
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL
    blocking: Annotated[
        bool, Field(description="Whether acquire() should block until available")
    ] = True
    timeout: Annotated[
        datetime.timedelta | None,
        Field(description="Maximum time to wait when blocking"),
    ] = DEFAULT_SOCKET_TIMEOUT

    # Computed fields (read-only, automatically calculated)
    @computed_field
    @property
    def instance_id(self) -> str:
        """Unique identifier for this semaphore instance."""
        if not hasattr(self, "_instance_id"):
            self._instance_id = str(uuid.uuid4())
        return self._instance_id

    @computed_field
    @property
    def semaphore_key(self) -> str:
        """Redis key for the semaphore sorted set."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}"

    @computed_field
    @property
    def holder_key(self) -> str:
        """Redis key for this instance's holder entry."""
        return f"{SEMAPHORE_HOLDER_KEY_PREFIX}{self.key}:{self.instance_id}"

    # Private state attributes (not part of the model)
    _acquired: bool = PrivateAttr(default=False)
    _auto_renew_task: asyncio.Task[None] | None = PrivateAttr(default=None)

    # Additional validation
    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: datetime.timedelta) -> datetime.timedelta:
        if v.total_seconds() <= 0:
            msg = "TTL must be positive"
            raise ValueError(msg)
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(
        cls, v: datetime.timedelta | None
    ) -> datetime.timedelta | None:
        if v is not None and v.total_seconds() <= 0:
            msg = "Timeout must be positive"
            raise ValueError(msg)
        return v

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
        timeout_seconds = self.timeout.total_seconds() if self.timeout else None

        while True:
            # Try to acquire using Redis sorted set for atomic operations
            acquired = await self._try_acquire()

            if acquired:
                self._acquired = True
                # Start auto-renewal task
                await self._start_auto_renew()
                _logger.debug(
                    "Acquired semaphore '%s' (instance: %s)",
                    self.key,
                    self.instance_id,
                )
                return True

            if not self.blocking:
                return False

            # Check timeout
            if timeout_seconds is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout_seconds:
                    if self.blocking:
                        raise SemaphoreAcquisitionError(
                            name=self.key, capacity=self.capacity
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
            raise SemaphoreNotAcquiredError(name=self.key)

        # Stop auto-renewal
        if self._auto_renew_task:
            await cancel_wait_task(self._auto_renew_task)
            self._auto_renew_task = None

        # Remove from Redis
        async with self.redis_client.redis.pipeline(transaction=True) as pipe:
            await pipe.zrem(self.semaphore_key, self.instance_id)
            await pipe.delete(self.holder_key)
            await pipe.execute()

        self._acquired = False
        _logger.debug(
            "Released semaphore '%s' (instance: %s)",
            self.key,
            self.instance_id,
        )

    async def _try_acquire(self) -> bool:
        """Atomically try to acquire the semaphore using Redis operations"""
        current_time = asyncio.get_event_loop().time()
        ttl_seconds = self.ttl.total_seconds()

        try:
            # Clean up expired entries first
            await self.redis_client.redis.zremrangebyscore(
                self.semaphore_key, "-inf", current_time - ttl_seconds
            )

            # Use Redis transactions for atomic operations
            async with self.redis_client.redis.pipeline(transaction=True) as pipe:
                # Watch the semaphore key for changes
                await pipe.watch(self.semaphore_key)

                # Check current count
                current_count = await self.redis_client.redis.zcard(self.semaphore_key)

                if current_count < self.capacity:
                    # Try to acquire
                    pipe.multi()
                    pipe.zadd(self.semaphore_key, {self.instance_id: current_time})
                    pipe.setex(self.holder_key, int(ttl_seconds), "1")
                    result = await pipe.execute()
                    return bool(result)

                # Cancel the transaction
                await pipe.reset()
                return False

        except Exception:
            _logger.exception(
                "Failed to acquire semaphore '%s'",
                self.key,
            )
            return False

    async def _start_auto_renew(self) -> None:
        started_event = asyncio.Event()

        @periodic(interval=self.ttl / 3, raise_on_error=True)
        async def _periodic_renewer() -> None:
            current_time = asyncio.get_event_loop().time()
            ttl_seconds = self.ttl.total_seconds()

            # Update timestamp in sorted set and refresh holder key
            async with self.redis_client.redis.pipeline(transaction=True) as pipe:
                await pipe.zadd(self.semaphore_key, {self.instance_id: current_time})
                await pipe.expire(self.holder_key, int(ttl_seconds))
                await pipe.execute()
            started_event.set()

        # Create the task for periodic renewal
        task_name = f"semaphore_renewal_{self.key}_{self.instance_id}"
        self._auto_renew_task = asyncio.create_task(_periodic_renewer(), name=task_name)
        # NOTE: this ensures the extend task ran once and ensure cancellation works
        await started_event.wait()

    async def get_current_count(self) -> int:
        """Get the current number of semaphore holders"""
        current_time = asyncio.get_event_loop().time()
        ttl_seconds = self.ttl.total_seconds()

        # Remove expired entries and count remaining
        async with self.redis_client.redis.pipeline(transaction=True) as pipe:
            await pipe.zremrangebyscore(
                self.semaphore_key, "-inf", current_time - ttl_seconds
            )
            await pipe.zcard(self.semaphore_key)
            results = await pipe.execute()

        return int(results[1])

    async def get_available_count(self) -> int:
        """Get the number of available semaphore slots"""
        current_count = await self.get_current_count()
        return max(0, self.capacity - current_count)

    # Context manager support
    async def __aenter__(self) -> "DistributedSemaphore":
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
            f"DistributedSemaphore(key={self.key!r}, "
            f"capacity={self.capacity}, acquired={self._acquired})"
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
            semaphore = DistributedSemaphore(
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
