import datetime
import logging
import uuid
from types import TracebackType
from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    computed_field,
    field_validator,
)
from redis.commands.core import AsyncScript
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_not_result,
    stop_after_delay,
    stop_never,
    wait_random_exponential,
)

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
    ACQUIRE_SEMAPHORE_SCRIPT,
    COUNT_SEMAPHORE_SCRIPT,
    RELEASE_SEMAPHORE_SCRIPT,
    RENEW_SEMAPHORE_SCRIPT,
    SCRIPT_BAD_EXIT_CODE,
    SCRIPT_OK_EXIT_CODE,
)

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
    instance_id: Annotated[
        str,
        Field(
            description="Unique instance identifier",
            default_factory=lambda: f"{uuid.uuid4()}",
        ),
    ] = DEFAULT_FACTORY

    # Private state attributes (not part of the model)
    _acquire_script: AsyncScript
    _count_script: AsyncScript
    _release_script: AsyncScript
    _renew_script: AsyncScript

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self._acquire_script = self.redis_client.redis.register_script(
            ACQUIRE_SEMAPHORE_SCRIPT
        )
        self._count_script = self.redis_client.redis.register_script(
            COUNT_SEMAPHORE_SCRIPT
        )
        self._release_script = self.redis_client.redis.register_script(
            RELEASE_SEMAPHORE_SCRIPT
        )
        self._renew_script = self.redis_client.redis.register_script(
            RENEW_SEMAPHORE_SCRIPT
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def semaphore_key(self) -> str:
        """Redis key for the semaphore sorted set."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holder_key(self) -> str:
        """Redis key for this instance's holder entry."""
        return f"{SEMAPHORE_HOLDER_KEY_PREFIX}{self.key}:{self.instance_id}"

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

        if not self.blocking:
            # Non-blocking: try once
            return await self._try_acquire()

        # Blocking
        @retry(
            wait=wait_random_exponential(min=0.1, max=2),
            reraise=True,
            stop=(
                stop_after_delay(self.blocking_timeout.total_seconds())
                if self.blocking_timeout
                else stop_never
            ),
            retry=retry_if_not_result(lambda acquired: acquired),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        )
        async def _blocking_acquire() -> bool:
            return await self._try_acquire()

        try:
            return await _blocking_acquire()
        except RetryError as exc:
            raise SemaphoreAcquisitionError(
                name=self.key, capacity=self.capacity
            ) from exc

    async def release(self) -> None:
        """
        Release the semaphore atomically using Lua script.

        Raises:
            SemaphoreNotAcquiredError: If semaphore was not acquired by this instance
        """
        ttl_seconds = int(self.ttl.total_seconds())

        # Execute the release Lua script atomically
        result = await self._release_script(
            keys=(
                self.semaphore_key,
                self.holder_key,
            ),
            args=(
                self.instance_id,
                str(ttl_seconds),
            ),
            client=self.redis_client.redis,
        )

        assert isinstance(result, list)  # nosec
        exit_code, status, current_count, expired_count = result
        result = status

        if result == "released":
            assert exit_code == SCRIPT_BAD_EXIT_CODE  # nosec
            _logger.debug(
                "Released semaphore '%s' (instance: %s, count: %s, expired: %s)",
                self.key,
                self.instance_id,
                current_count,
                expired_count,
            )
        else:
            # Instance wasn't in the semaphore set - this shouldn't happen
            # but let's handle it gracefully
            assert exit_code == SCRIPT_OK_EXIT_CODE  # nosec
            raise SemaphoreNotAcquiredError(name=self.key)

    async def _try_acquire(self) -> bool:
        ttl_seconds = int(self.ttl.total_seconds())

        # Execute the Lua script atomically
        result = await self._acquire_script(
            keys=(self.semaphore_key, self.holder_key),
            args=(self.instance_id, str(self.capacity), str(ttl_seconds)),
            client=self.redis_client.redis,
        )

        # Lua script returns: [exit_code, status, current_count, expired_count]
        assert isinstance(result, list)  # nosec
        exit_code, status, current_count, expired_count = result

        if exit_code == SCRIPT_OK_EXIT_CODE:
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

    async def reacquire(self) -> None:
        """
        Atomically renew a semaphore entry using Lua script.

        This function is intended to be called by decorators or external renewal mechanisms.


        Raises:
            SemaphoreLostError: If the semaphore was lost or expired
        """

        ttl_seconds = int(self.ttl.total_seconds())

        # Execute the renewal Lua script atomically
        result = await self._renew_script(
            keys=(self.semaphore_key, self.holder_key),
            args=(
                self.instance_id,
                str(ttl_seconds),
            ),
            client=self.redis_client.redis,
        )

        assert isinstance(result, list)  # nosec
        exit_code, status, current_count, expired_count = result

        # Lua script returns: 'renewed' or status message
        if status == "renewed":
            assert exit_code == SCRIPT_OK_EXIT_CODE  # nosec
            _logger.debug(
                "Renewed semaphore '%s' (instance: %s, count: %s, expired: %s)",
                self.key,
                self.instance_id,
                current_count,
                expired_count,
            )
        else:
            assert exit_code == SCRIPT_BAD_EXIT_CODE  # nosec
            if status == "expired":
                _logger.warning(
                    "Semaphore '%s' holder key expired (instance: %s, count: %s, expired: %s)",
                    self.key,
                    self.instance_id,
                    current_count,
                    expired_count,
                )
            elif status == "not_held":
                _logger.warning(
                    "Semaphore '%s' not held (instance: %s, count: %s, expired: %s)",
                    self.key,
                    self.instance_id,
                    current_count,
                    expired_count,
                )

            raise SemaphoreLostError(name=self.key, instance_id=self.instance_id)

    async def get_current_count(self) -> int:
        """Get the current number of semaphore holders"""
        ttl_seconds = int(self.ttl.total_seconds())

        # Execute the count Lua script atomically
        result = await self._count_script(
            keys=(self.semaphore_key,),
            args=(str(ttl_seconds),),
            client=self.redis_client.redis,
        )

        assert isinstance(result, list)  # nosec
        current_count, expired_count = result

        if int(expired_count) > 0:
            _logger.debug(
                "Cleaned up %s expired entries from semaphore '%s'",
                expired_count,
                self.key,
            )

        return int(current_count)

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
        await self.release()
