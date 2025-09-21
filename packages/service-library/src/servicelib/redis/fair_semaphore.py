"""Fair distributed semaphore using token pool with crash recovery."""

import asyncio
import datetime
import logging
import uuid
from typing import ClassVar

from pydantic import BaseModel, Field, PositiveInt, computed_field, field_validator
from redis.commands.core import AsyncScript

from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_SEMAPHORE_TTL,
    DEFAULT_SOCKET_TIMEOUT,
    SEMAPHORE_HOLDER_KEY_PREFIX,
    SEMAPHORE_KEY_PREFIX,
)
from ._errors import (
    SemaphoreAcquisitionError,
    SemaphoreLostError,
    SemaphoreNotAcquiredError,
)
from ._semaphore_lua import (
    ACQUIRE_FAIR_SEMAPHORE_V2_SCRIPT,
    CLEANUP_FAIR_SEMAPHORE_V2_SCRIPT,
    COUNT_FAIR_SEMAPHORE_V2_SCRIPT,
    RELEASE_FAIR_SEMAPHORE_V2_SCRIPT,
    RENEW_FAIR_SEMAPHORE_V2_SCRIPT,
    SCRIPT_OK_EXIT_CODE,
)

_logger = logging.getLogger(__name__)


class FairSemaphore(BaseModel):
    """
    A fair distributed semaphore using Redis token pool with BRPOP.

    Features:
    - True FIFO fairness via BRPOP blocking operations
    - Crash recovery through TTL-based cleanup
    - No Python-side retry logic needed
    - Automatic token pool management
    """

    capacity: PositiveInt = Field(description="Maximum number of concurrent holders")
    key: str = Field(description="Unique semaphore identifier")
    ttl: datetime.timedelta = Field(
        default=DEFAULT_SEMAPHORE_TTL,
        description="How long a holder can keep the semaphore",
    )
    timeout: datetime.timedelta = Field(
        default=DEFAULT_SOCKET_TIMEOUT,
        description="How long to block waiting for semaphore (0 = infinite)",
    )
    cleanup_interval: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=30),
        description="How often to run cleanup to recover crashed client tokens",
    )
    enable_auto_cleanup: bool = Field(
        default=True, description="Whether to automatically run background cleanup"
    )

    # Internal state
    instance_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8],
        description="Unique identifier for this semaphore instance",
    )
    _acquired: bool = Field(default=False, exclude=True)
    _token: str | None = Field(default=None, exclude=True)
    _redis_client: RedisClientSDK | None = Field(default=None, exclude=True)
    _cleanup_task: asyncio.Task | None = Field(default=None, exclude=True)

    # Class-level script storage
    _acquire_script: ClassVar[AsyncScript | None] = None
    _release_script: ClassVar[AsyncScript | None] = None
    _cleanup_script: ClassVar[AsyncScript | None] = None
    _renew_script: ClassVar[AsyncScript | None] = None
    _count_script: ClassVar[AsyncScript | None] = None

    @computed_field
    @property
    def tokens_key(self) -> str:
        """Redis key for the token pool LIST."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}:tokens"

    @computed_field
    @property
    def holders_key(self) -> str:
        """Redis key for the holders SET."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}:holders"

    @computed_field
    @property
    def holder_key(self) -> str:
        """Redis key for this instance's holder TTL key."""
        return f"{SEMAPHORE_HOLDER_KEY_PREFIX}{self.key}:{self.instance_id}"

    @computed_field
    @property
    def holder_prefix(self) -> str:
        """Prefix for holder keys (used in cleanup)."""
        return f"{SEMAPHORE_HOLDER_KEY_PREFIX}{self.key}:"

    @field_validator("ttl", "timeout", "cleanup_interval")
    @classmethod
    def validate_positive_timedelta(cls, v: datetime.timedelta) -> datetime.timedelta:
        if v.total_seconds() <= 0:
            raise ValueError("Timedelta must be positive")
        return v

    def model_post_init(self, __context) -> None:
        """Initialize Redis client."""
        if self._redis_client is None:
            self._redis_client = RedisClientSDK()

    async def _load_scripts(self) -> None:
        """Load Lua scripts into Redis."""
        if self.__class__._acquire_script is None:
            redis = await self._redis_client.get_redis_client()

            self.__class__._acquire_script = redis.register_script(
                ACQUIRE_FAIR_SEMAPHORE_V2_SCRIPT
            )
            self.__class__._release_script = redis.register_script(
                RELEASE_FAIR_SEMAPHORE_V2_SCRIPT
            )
            self.__class__._cleanup_script = redis.register_script(
                CLEANUP_FAIR_SEMAPHORE_V2_SCRIPT
            )
            self.__class__._renew_script = redis.register_script(
                RENEW_FAIR_SEMAPHORE_V2_SCRIPT
            )
            self.__class__._count_script = redis.register_script(
                COUNT_FAIR_SEMAPHORE_V2_SCRIPT
            )

    async def _start_cleanup_task(self) -> None:
        """Start the background cleanup task if enabled."""
        if self.enable_auto_cleanup and (
            self._cleanup_task is None or self._cleanup_task.done()
        ):
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Background task to periodically clean up crashed client tokens."""
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval.total_seconds())
                try:
                    await self._recover_crashed_tokens()
                except Exception as e:
                    _logger.warning(f"Cleanup failed for semaphore {self.key}: {e}")
        except asyncio.CancelledError:
            _logger.debug(f"Cleanup task cancelled for semaphore {self.key}")

    async def _recover_crashed_tokens(self) -> dict:
        """Recover tokens from crashed clients."""
        await self._load_scripts()

        result = await self.__class__._cleanup_script(
            keys=[self.tokens_key, self.holders_key, self.holder_prefix],
            args=[self.capacity],
        )

        recovered_tokens, current_holders, available_tokens, total_cleaned = result

        cleanup_stats = {
            "recovered_tokens": recovered_tokens,
            "current_holders": current_holders,
            "available_tokens": available_tokens,
            "total_cleaned": total_cleaned,
        }

        if recovered_tokens > 0 or total_cleaned > 0:
            _logger.info(
                f"Semaphore cleanup for '{self.key}': "
                f"recovered {recovered_tokens} tokens, "
                f"cleaned {total_cleaned} crashed holders, "
                f"current state: {current_holders} holders, {available_tokens} available"
            )

        return cleanup_stats

    async def acquire(self) -> bool:
        """
        Acquire the semaphore using blocking Redis operation.

        This method blocks until a semaphore slot becomes available or timeout.
        Uses Redis BRPOP for true FIFO fairness with no starvation possible.

        Returns:
            True if acquired successfully

        Raises:
            SemaphoreAcquisitionError: If acquisition fails or times out
        """
        await self._load_scripts()

        if self.enable_auto_cleanup:
            await self._start_cleanup_task()

        if self._acquired:
            raise SemaphoreAcquisitionError(
                "Semaphore already acquired by this instance"
            )

        ttl_seconds = max(1, int(self.ttl.total_seconds()))
        timeout_seconds = int(self.timeout.total_seconds())

        _logger.debug(
            f"Attempting to acquire fair semaphore '{self.key}' "
            f"(timeout: {timeout_seconds}s, ttl: {ttl_seconds}s)"
        )

        try:
            result = await self.__class__._acquire_script(
                keys=[self.tokens_key, self.holders_key, self.holder_key],
                args=[self.instance_id, self.capacity, ttl_seconds, timeout_seconds],
            )

            exit_code, status, token, current_count = result

            _logger.debug(
                f"Fair semaphore acquisition result for '{self.key}'",
                extra={
                    "instance_id": self.instance_id,
                    "exit_code": exit_code,
                    "status": status,
                    "token": token,
                    "current_count": current_count,
                },
            )

            if exit_code == SCRIPT_OK_EXIT_CODE:  # Success
                self._acquired = True
                self._token = token
                _logger.info(
                    f"Acquired fair semaphore '{self.key}' with token '{token}'"
                )
                return True
            # Timeout or error
            raise SemaphoreAcquisitionError(f"Failed to acquire semaphore: {status}")

        except Exception as e:
            _logger.error(f"Error acquiring semaphore '{self.key}': {e}")
            raise SemaphoreAcquisitionError(f"Redis error during acquisition: {e}")

    async def release(self) -> bool:
        """
        Release the semaphore and return token to pool.

        This automatically makes the semaphore available to waiting clients.
        The token is returned to the pool, unblocking any BRPOP waiters.

        Returns:
            True if released successfully

        Raises:
            SemaphoreNotAcquiredError: If semaphore not held by this instance
        """
        await self._load_scripts()

        if not self._acquired:
            raise SemaphoreNotAcquiredError("Semaphore not acquired by this instance")

        try:
            result = await self.__class__._release_script(
                keys=[self.tokens_key, self.holders_key, self.holder_key],
                args=[self.instance_id],
            )

            exit_code, status, current_count = result

            _logger.debug(
                f"Fair semaphore release result for '{self.key}'",
                extra={
                    "instance_id": self.instance_id,
                    "exit_code": exit_code,
                    "status": status,
                    "current_count": current_count,
                },
            )

            if exit_code == SCRIPT_OK_EXIT_CODE:  # Success
                self._acquired = False
                _logger.info(
                    f"Released fair semaphore '{self.key}' with token '{self._token}'"
                )
                self._token = None
                return True
            # Error
            self._acquired = False  # Mark as not acquired even on error
            raise SemaphoreNotAcquiredError(f"Failed to release semaphore: {status}")

        except Exception as e:
            _logger.error(f"Error releasing semaphore '{self.key}': {e}")
            self._acquired = False  # Mark as not acquired on error
            raise SemaphoreNotAcquiredError(f"Redis error during release: {e}")

    async def renew(self) -> bool:
        """
        Renew the semaphore TTL.

        Returns:
            True if renewed successfully

        Raises:
            SemaphoreLostError: If semaphore was lost (expired or not held)
        """
        await self._load_scripts()

        if not self._acquired:
            raise SemaphoreNotAcquiredError("Semaphore not acquired by this instance")

        ttl_seconds = max(1, int(self.ttl.total_seconds()))

        try:
            result = await self.__class__._renew_script(
                keys=[self.holders_key, self.holder_key],
                args=[self.instance_id, ttl_seconds],
            )

            exit_code, status, current_count = result

            if exit_code == SCRIPT_OK_EXIT_CODE:
                _logger.debug(f"Renewed semaphore '{self.key}' TTL")
                return True
            self._acquired = False
            raise SemaphoreLostError(f"Semaphore was lost: {status}")

        except Exception as e:
            _logger.error(f"Error renewing semaphore '{self.key}': {e}")
            # Don't mark as not acquired on network errors
            raise SemaphoreLostError(f"Redis error during renewal: {e}")

    async def count(self) -> dict:
        """
        Get semaphore usage statistics.

        Returns:
            Dictionary with current_holders, available_tokens, capacity
        """
        await self._load_scripts()

        result = await self.__class__._count_script(
            keys=[self.holders_key, self.tokens_key], args=[self.capacity]
        )

        current_holders, available_tokens, capacity = result

        return {
            "current_holders": current_holders,
            "available_tokens": available_tokens,
            "capacity": capacity,
            "utilization": current_holders / capacity if capacity > 0 else 0.0,
        }

    async def health_check(self) -> dict:
        """Get comprehensive semaphore health information."""
        count_info = await self.count()
        cleanup_stats = await self._recover_crashed_tokens()

        total_accounted = count_info["current_holders"] + count_info["available_tokens"]

        return {
            **count_info,
            **cleanup_stats,
            "total_accounted": total_accounted,
            "is_healthy": total_accounted == self.capacity,
            "cleanup_enabled": self.enable_auto_cleanup,
            "instance_acquired": self._acquired,
        }

    async def force_cleanup(self) -> dict:
        """Manually trigger cleanup and return recovery statistics."""
        return await self._recover_crashed_tokens()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._acquired:
            try:
                await self.release()
            except Exception as e:
                _logger.error(f"Error releasing semaphore in __aexit__: {e}")

        # Cancel cleanup task when exiting
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    @property
    def acquired(self) -> bool:
        """Check if semaphore is currently acquired."""
        return self._acquired
