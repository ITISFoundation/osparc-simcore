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

# Lua script for atomic semaphore acquisition
ACQUIRE_SEMAPHORE_SCRIPT = """
-- Atomic semaphore acquisition script
-- KEYS[1]: semaphore_key (ZSET storing holders with timestamps)
-- KEYS[2]: holder_key (individual holder TTL key)
-- ARGV[1]: instance_id
-- ARGV[2]: capacity (max concurrent holders)
-- ARGV[3]: ttl_seconds
-- ARGV[4]: current_time (Redis server time)

local semaphore_key = KEYS[1]
local holder_key = KEYS[2]
local instance_id = ARGV[1]
local capacity = tonumber(ARGV[2])
local ttl_seconds = tonumber(ARGV[3])
local current_time = tonumber(ARGV[4])

-- Step 1: Clean up expired entries
local expiry_threshold = current_time - ttl_seconds
local expired_count = redis.call('ZREMRANGEBYSCORE', semaphore_key, '-inf', expiry_threshold)

-- Step 2: Check current capacity after cleanup
local current_count = redis.call('ZCARD', semaphore_key)

-- Step 3: Try to acquire if under capacity
if current_count < capacity then
    -- Atomically add to semaphore and set holder key
    redis.call('ZADD', semaphore_key, current_time, instance_id)
    redis.call('SETEX', holder_key, ttl_seconds, '1')

    return {1, 'acquired', current_count + 1, expired_count}
else
    return {0, 'capacity_full', current_count, expired_count}
end
"""


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

    async def get_redis_time(self) -> float:
        """
        Get the current Redis server time as a float timestamp.

        This provides a synchronized timestamp across all Redis clients,
        avoiding clock drift issues between different machines.

        Returns:
            Current Redis server time as seconds since Unix epoch (float)
        """
        time_response = await self.redis_client.redis.time()
        # Redis TIME returns (seconds, microseconds) tuple
        seconds, microseconds = time_response
        return float(seconds) + float(microseconds) / 1_000_000

    async def _acquire_with_lua(self) -> bool:
        """
        Try to acquire the semaphore using atomic Lua script.

        Returns:
            True if acquired successfully, False otherwise
        """
        current_time = await self.get_redis_time()
        ttl_seconds = int(self.ttl.total_seconds())

        try:
            # Execute the Lua script atomically
            result = await self.redis_client.redis.eval(
                ACQUIRE_SEMAPHORE_SCRIPT,
                2,  # Number of keys
                self.semaphore_key,
                self.holder_key,
                self.instance_id,
                str(self.capacity),
                str(ttl_seconds),
                str(current_time),
            )

            # Lua script returns: [success, status, current_count, expired_count]
            result_list = list(result) if isinstance(result, list | tuple) else [result]
            success, status, current_count, expired_count = result_list

            if success == 1:
                _logger.debug(
                    "Acquired semaphore '%s' (instance: %s, count: %s, expired: %s)",
                    self.key,
                    self.instance_id,
                    current_count,
                    expired_count,
                )
                return True

            _logger.debug(
                "Failed to acquire semaphore '%s' - %s (count: %s, expired: %s)",
                self.key,
                status,
                current_count,
                expired_count,
            )
            return False

        except Exception as exc:
            _logger.warning(
                "Error executing acquisition Lua script for semaphore '%s': %s",
                self.key,
                exc,
            )
            # Fallback to original implementation
            return await self._try_acquire_fallback()

    async def _try_acquire_fallback(self) -> bool:
        """Fallback implementation using Redis transactions (original method)"""
        current_time = await self.get_redis_time()
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

    async def _try_acquire(self) -> bool:
        """Try to acquire the semaphore using Lua script with fallback"""
        return await self._acquire_with_lua()

    async def get_current_count(self) -> int:
        """Get the current number of semaphore holders"""
        current_time = await self.get_redis_time()
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
