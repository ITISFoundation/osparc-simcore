import asyncio
import datetime
import logging
import uuid
from types import TracebackType
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    PrivateAttr,
    computed_field,
    field_validator,
)
from tenacity import (
    RetryError,
    retry,
    retry_if_not_result,
    stop_after_delay,
    stop_never,
    wait_fixed,
)

from ..logging_utils import log_catch
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
    Warning: This should only be used directly via the decorator

    A distributed semaphore implementation using Redis.

    This semaphore allows limiting the number of concurrent operations across
    multiple processes/instances using Redis as the coordination backend.

    Args:
        redis_client: Redis client for coordination
        key: Unique identifier for the semaphore
        capacity: Maximum number of concurrent holders
        ttl: Time-to-live for semaphore entries (auto-cleanup)
        blocking: Whether acquire() should block until available
        blocking_timeout: Maximum time to wait when blocking (None = no timeout)

    Example:
        async with DistributedSemaphore(
            redis_client, "my_resource", capacity=3
        ):
            # Only 3 instances can execute this block concurrently
            await do_limited_work()
    """

    model_config = {
        "arbitrary_types_allowed": True,  # For RedisClientSDK
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
    blocking_timeout: Annotated[
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

    # Additional validation
    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: datetime.timedelta) -> datetime.timedelta:
        if v.total_seconds() <= 0:
            msg = "TTL must be positive"
            raise ValueError(msg)
        return v

    @field_validator("blocking_timeout")
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

        if not self.blocking:
            # Non-blocking: try once
            self._acquired = await self._try_acquire()
            return self._acquired

        # Blocking
        @retry(
            wait=wait_fixed(0.1),
            reraise=True,
            stop=(
                stop_after_delay(self.blocking_timeout.total_seconds())
                if self.blocking_timeout
                else stop_never
            ),
            retry=retry_if_not_result(lambda acquired: acquired),
        )
        async def _blocking_acquire() -> bool:
            return await self._try_acquire()

        try:
            self._acquired = await _blocking_acquire()
            return self._acquired
        except RetryError as exc:
            raise SemaphoreAcquisitionError(
                name=self.key, capacity=self.capacity
            ) from exc

    async def release(self) -> None:
        """
        Release the semaphore.

        Raises:
            SemaphoreNotAcquiredError: If semaphore was not acquired by this instance
        """
        if not self._acquired:
            raise SemaphoreNotAcquiredError(name=self.key)

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

    def is_acquired(self) -> bool:
        """Check if this semaphore instance is currently acquired."""
        return self._acquired

    async def _try_acquire(self) -> bool:
        """Atomically try to acquire the semaphore using Redis operations"""
        current_time = asyncio.get_event_loop().time()
        ttl_seconds = self.ttl.total_seconds()

        with log_catch(_logger, reraise=False):
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

        return False

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
