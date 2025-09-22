"""Pure Python BRPOP-based fair semaphore implementation."""

import asyncio
import datetime
import logging
import uuid
from types import TracebackType
from typing import Annotated, ClassVar

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    computed_field,
    field_validator,
)
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
    CLEANUP_FAIR_SEMAPHORE_V2_SCRIPT,
    COUNT_FAIR_SEMAPHORE_V2_SCRIPT,
    REGISTER_SEMAPHORE_HOLDER_SCRIPT,
    RELEASE_FAIR_SEMAPHORE_V2_SCRIPT,
    RENEW_FAIR_SEMAPHORE_V2_SCRIPT,
    SCRIPT_OK_EXIT_CODE,
)

_logger = logging.getLogger(__name__)


class PureBRPOPSemaphore(BaseModel):
    """
    A pure Python BRPOP-based fair semaphore implementation.

    This approach uses Redis BRPOP directly from Python for true blocking fairness,
    with minimal Lua scripts only for registration and cleanup.

    Features:
    - True FIFO fairness guaranteed by Redis BRPOP
    - Native Redis blocking - no Python-side polling needed
    - Crash recovery through TTL-based cleanup
    - Maximum simplicity and reliability
    """

    model_config = {
        "arbitrary_types_allowed": True,  # For RedisClientSDK
    }

    # Configuration fields
    redis_client: RedisClientSDK
    key: Annotated[
        str, Field(min_length=1, description="Unique identifier for the semaphore")
    ]
    capacity: Annotated[
        PositiveInt, Field(description="Maximum number of concurrent holders")
    ]
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL
    blocking_timeout: Annotated[
        datetime.timedelta | None,
        Field(description="Maximum time to wait when blocking"),
    ] = DEFAULT_SOCKET_TIMEOUT

    enable_auto_cleanup: bool = Field(
        default=True,
        description="Whether to enable automatic cleanup of crashed holders",
    )

    instance_id: Annotated[
        str,
        Field(
            description="Unique instance identifier",
            default_factory=lambda: f"{uuid.uuid4()}",
        ),
    ] = DEFAULT_FACTORY

    # Class-level script storage
    register_script: ClassVar[AsyncScript | None] = None
    release_script: ClassVar[AsyncScript | None] = None
    renew_script: ClassVar[AsyncScript | None] = None
    count_script: ClassVar[AsyncScript | None] = None
    cleanup_script: ClassVar[AsyncScript | None] = None

    # Private state
    _acquired: bool = False
    _token: str | None = None
    _cleanup_task: asyncio.Task | None = None

    @classmethod
    def _register_scripts(cls, redis_client: RedisClientSDK) -> None:
        """Register minimal Lua scripts with Redis."""
        if cls.register_script is None:
            cls.register_script = redis_client.redis.register_script(
                REGISTER_SEMAPHORE_HOLDER_SCRIPT
            )
            cls.release_script = redis_client.redis.register_script(
                RELEASE_FAIR_SEMAPHORE_V2_SCRIPT
            )
            cls.renew_script = redis_client.redis.register_script(
                RENEW_FAIR_SEMAPHORE_V2_SCRIPT
            )
            cls.count_script = redis_client.redis.register_script(
                COUNT_FAIR_SEMAPHORE_V2_SCRIPT
            )
            cls.cleanup_script = redis_client.redis.register_script(
                CLEANUP_FAIR_SEMAPHORE_V2_SCRIPT
            )

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self.__class__._register_scripts(self.redis_client)

        # Start cleanup task if enabled
        if self.enable_auto_cleanup:
            self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start background cleanup task for crashed holders."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Background task to clean up crashed holders."""
        try:
            while True:
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                try:
                    await self._recover_crashed_tokens()
                except Exception as e:
                    _logger.warning(f"Cleanup failed for semaphore {self.key}: {e}")
        except asyncio.CancelledError:
            pass

    async def _recover_crashed_tokens(self) -> None:
        """Recover tokens from crashed clients."""
        cls = type(self)
        assert cls.cleanup_script is not None

        result = await cls.cleanup_script(
            keys=[self.tokens_key, self.holders_key, self.holder_prefix],
            args=[self.capacity],
            client=self.redis_client.redis,
        )

        recovered_tokens, current_holders, available_tokens, total_cleaned = result

        if recovered_tokens > 0 or total_cleaned > 0:
            _logger.info(
                f"Recovered {recovered_tokens} tokens from {total_cleaned} crashed holders "
                f"for semaphore '{self.key}'"
            )

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
        """Redis key for this instance's holder entry."""
        return f"{SEMAPHORE_HOLDER_KEY_PREFIX}{self.key}:{self.instance_id}"

    @computed_field
    @property
    def holder_prefix(self) -> str:
        """Prefix for holder keys (used in cleanup)."""
        return f"{SEMAPHORE_HOLDER_KEY_PREFIX}{self.key}:"

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: datetime.timedelta) -> datetime.timedelta:
        if v.total_seconds() <= 0:
            raise ValueError("TTL must be positive")
        return v

    @field_validator("blocking_timeout")
    @classmethod
    def validate_timeout(
        cls, v: datetime.timedelta | None
    ) -> datetime.timedelta | None:
        if v is not None and v.total_seconds() <= 0:
            raise ValueError("Timeout must be positive")
        return v

    async def acquire(self) -> bool:
        """
        Acquire the semaphore using pure Python BRPOP.

        This is the cleanest possible approach:
        1. Call Redis BRPOP directly from Python (guaranteed FIFO fairness)
        2. Use minimal Lua script only to register as holder
        3. No complex retry logic or notifications needed

        Returns:
            True if acquired successfully

        Raises:
            SemaphoreAcquisitionError: If acquisition fails or times out
        """
        if self._acquired:
            raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)

        timeout_seconds = (
            int(self.blocking_timeout.total_seconds()) if self.blocking_timeout else 0
        )
        ttl_seconds = int(self.ttl.total_seconds())

        _logger.debug(
            f"Attempting to acquire semaphore '{self.key}' using BRPOP "
            f"(timeout: {timeout_seconds}s)"
        )

        try:
            # Use Redis BRPOP directly from Python - this is perfectly legal!
            # BRPOP blocks until a token is available or timeout occurs
            result = await self.redis_client.redis.brpop(
                self.tokens_key, timeout=timeout_seconds
            )

            if result is None:
                # Timeout occurred
                raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)

            # result is (key, token) tuple
            _, token = result
            token = token.decode("utf-8") if isinstance(token, bytes) else token

            # Register as holder using minimal Lua script
            cls = type(self)
            assert cls.register_script is not None

            register_result = await cls.register_script(
                keys=[self.tokens_key, self.holders_key, self.holder_key],
                args=[self.instance_id, self.capacity, ttl_seconds, token],
                client=self.redis_client.redis,
            )

            exit_code, status, current_count = register_result

            if exit_code == SCRIPT_OK_EXIT_CODE:
                self._acquired = True
                self._token = token

                _logger.info(
                    f"Acquired semaphore '{self.key}' with token '{token}' "
                    f"(instance: {self.instance_id}, count: {current_count})"
                )
                return True
            else:
                # Registration failed - this shouldn't happen but be safe
                # Return the token to the pool
                await self.redis_client.redis.lpush(self.tokens_key, token)
                raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)

        except TimeoutError:
            raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)
        except Exception as e:
            _logger.error(f"Error acquiring semaphore '{self.key}': {e}")
            raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)

    async def release(self) -> None:
        """
        Release the semaphore and return token to pool.

        Raises:
            SemaphoreNotAcquiredError: If semaphore was not acquired by this instance
        """
        if not self._acquired:
            raise SemaphoreNotAcquiredError(name=self.key)

        try:
            # Use existing release script
            cls = type(self)
            assert cls.release_script is not None

            result = await cls.release_script(
                keys=[self.tokens_key, self.holders_key, self.holder_key],
                args=[self.instance_id],
                client=self.redis_client.redis,
            )

            exit_code, status, current_count = result

            if exit_code == SCRIPT_OK_EXIT_CODE:
                released_token = self._token
                self._acquired = False
                self._token = None

                _logger.info(
                    f"Released semaphore '{self.key}' with token '{released_token}' "
                    f"(instance: {self.instance_id}, count: {current_count})"
                )
                return

            # Release failed
            _logger.error(
                f"Failed to release semaphore '{self.key}' - {status} "
                f"(instance: {self.instance_id}, count: {current_count})"
            )
            # Mark as not acquired anyway to prevent stuck state
            self._acquired = False
            self._token = None
            raise SemaphoreNotAcquiredError(name=self.key)

        except Exception as e:
            _logger.error(f"Error releasing semaphore '{self.key}': {e}")
            # Mark as not acquired to prevent stuck state
            self._acquired = False
            self._token = None
            raise SemaphoreNotAcquiredError(name=self.key)

    async def renew(self) -> None:
        """
        Renew the semaphore TTL.

        Raises:
            SemaphoreLostError: If the semaphore was lost or expired
        """
        if not self._acquired:
            raise SemaphoreNotAcquiredError(name=self.key)

        ttl_seconds = int(self.ttl.total_seconds())

        try:
            cls = type(self)
            assert cls.renew_script is not None

            result = await cls.renew_script(
                keys=[self.holders_key, self.holder_key],
                args=[self.instance_id, ttl_seconds],
                client=self.redis_client.redis,
            )

            exit_code, status, current_count = result

            if exit_code == SCRIPT_OK_EXIT_CODE:
                _logger.debug(f"Renewed semaphore '{self.key}' TTL")
                return

            # Renewal failed - semaphore was lost
            _logger.warning(
                f"Semaphore '{self.key}' was lost during renewal - {status} "
                f"(instance: {self.instance_id})"
            )
            self._acquired = False
            self._token = None
            raise SemaphoreLostError(name=self.key, instance_id=self.instance_id)

        except Exception as e:
            _logger.error(f"Error renewing semaphore '{self.key}': {e}")
            raise SemaphoreLostError(name=self.key, instance_id=self.instance_id)

    async def get_current_count(self) -> int:
        """Get the current number of semaphore holders."""
        cls = type(self)
        assert cls.count_script is not None

        result = await cls.count_script(
            keys=[self.holders_key, self.tokens_key],
            args=[self.capacity],
            client=self.redis_client.redis,
        )

        current_holders, available_tokens, capacity = result
        return int(current_holders)

    async def get_available_count(self) -> int:
        """Get the number of available semaphore slots."""
        current_count = await self.get_current_count()
        return max(0, self.capacity - current_count)

    @property
    def acquired(self) -> bool:
        """Check if semaphore is currently acquired."""
        return self._acquired

    # Context manager support
    async def __aenter__(self) -> "PureBRPOPSemaphore":
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

        # Clean up background task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
