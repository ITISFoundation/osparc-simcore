import datetime
import logging
import uuid
from types import TracebackType
from typing import Annotated, ClassVar

import redis.exceptions
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
    SEMAPHORE_KEY_PREFIX,
)
from ._errors import (
    SemaphoreAcquisitionError,
    SemaphoreLostError,
    SemaphoreNotAcquiredError,
)
from ._semaphore_lua import (
    ACQUIRE_FAIR_SEMAPHORE_V2_SCRIPT,
    COUNT_FAIR_SEMAPHORE_V2_SCRIPT,
    REGISTER_FAIR_SEMAPHORE_SCRIPT,
    RELEASE_FAIR_SEMAPHORE_V2_SCRIPT,
    RENEW_FAIR_SEMAPHORE_V2_SCRIPT,
    SCRIPT_BAD_EXIT_CODE,
    SCRIPT_OK_EXIT_CODE,
)
from ._utils import handle_redis_returns_union_types

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

    # Class and/or Private state attributes (not part of the model)
    register_semaphore: ClassVar[AsyncScript | None] = None
    acquire_script: ClassVar[AsyncScript | None] = None
    count_script: ClassVar[AsyncScript | None] = None
    release_script: ClassVar[AsyncScript | None] = None
    renew_script: ClassVar[AsyncScript | None] = None

    @classmethod
    def _register_scripts(cls, redis_client: RedisClientSDK) -> None:
        """Register Lua scripts with Redis if not already done.
        This is done once per class, not per instance. Internally the Redis client
        caches the script SHA, so this is efficient. Even if called multiple times,
        the script is only registered once."""
        if cls.acquire_script is None:
            cls.register_semaphore = redis_client.redis.register_script(
                REGISTER_FAIR_SEMAPHORE_SCRIPT
            )
            cls.acquire_script = redis_client.redis.register_script(
                ACQUIRE_FAIR_SEMAPHORE_V2_SCRIPT
            )
            cls.count_script = redis_client.redis.register_script(
                COUNT_FAIR_SEMAPHORE_V2_SCRIPT
            )
            cls.release_script = redis_client.redis.register_script(
                RELEASE_FAIR_SEMAPHORE_V2_SCRIPT
            )
            cls.renew_script = redis_client.redis.register_script(
                RENEW_FAIR_SEMAPHORE_V2_SCRIPT
            )

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self.__class__._register_scripts(self.redis_client)  # noqa: SLF001

    @computed_field  # type: ignore[prop-decorator]
    @property
    def semaphore_key(self) -> str:
        """Redis key for the semaphore sorted set."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tokens_key(self) -> str:
        """Redis key for the token pool LIST."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}:tokens"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holders_key(self) -> str:
        """Redis key for the holders SET."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}:holders"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holder_key(self) -> str:
        """Redis key for this instance's holder entry."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}:holders_:{self.instance_id}"

    @computed_field
    @property
    def holder_prefix(self) -> str:
        """Prefix for holder keys (used in cleanup)."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}:holders_:"

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

    async def _initialize_semaphore(self) -> None:
        """Initializes the semaphore in Redis if not already done."""
        ttl_seconds = int(self.ttl.total_seconds())
        cls = type(self)
        assert cls.register_semaphore is not None  # nosec
        await cls.register_semaphore(  # pylint: disable=not-callable
            keys=[self.tokens_key, self.holders_key],
            args=[self.capacity, ttl_seconds],
            client=self.redis_client.redis,
        )

    async def acquire(self) -> bool:
        """
        Acquire the semaphore.

        Returns:
            True if acquired successfully, False if not acquired and non-blocking

        Raises:
            SemaphoreAcquisitionError: If acquisition fails and blocking=True
        """

        if await self.is_acquired():
            _logger.debug(
                "Semaphore '%s' already acquired by this instance (instance: %s)",
                self.key,
                self.instance_id,
            )
            return True

        ttl_seconds = int(self.ttl.total_seconds())
        blocking_timeout_seconds = 0.001
        if self.blocking:
            blocking_timeout_seconds = (
                self.blocking_timeout.total_seconds() if self.blocking_timeout else 0
            )

        await self._initialize_semaphore()

        try:
            # this is blocking pop with timeout
            tokens_key_token: list[str] = await handle_redis_returns_union_types(
                self.redis_client.redis.brpop(
                    [self.tokens_key], timeout=blocking_timeout_seconds
                )
            )
        except redis.exceptions.TimeoutError as e:
            _logger.debug(
                "Timeout acquiring semaphore '%s' (instance: %s)",
                self.key,
                self.instance_id,
            )
            if self.blocking:
                raise SemaphoreAcquisitionError(
                    name=self.key, capacity=self.capacity
                ) from e
            return False

        assert len(tokens_key_token) == 2  # nosec
        assert tokens_key_token[0] == self.tokens_key  # nosec
        token = tokens_key_token[1]

        cls = type(self)
        assert cls.acquire_script is not None  # nosec
        result = await cls.acquire_script(  # pylint: disable=not-callable
            keys=[self.holders_key, self.holder_key],
            args=[
                token,
                self.instance_id,
                ttl_seconds,
            ],
            client=self.redis_client.redis,
        )

        # Lua script returns: [exit_code, status, current_count, expired_count]
        assert isinstance(result, list)  # nosec
        exit_code, status, token, current_count = result

        if exit_code == SCRIPT_OK_EXIT_CODE:
            _logger.debug(
                "Acquired semaphore '%s' with token %s (instance: %s, count: %s)",
                self.key,
                token,
                self.instance_id,
                current_count,
            )
            return True

        if status == "timeout":
            if self.blocking:
                _logger.debug(
                    "Timeout acquiring semaphore '%s' (instance: %s, count: %s)",
                    self.key,
                    self.instance_id,
                    current_count,
                )
                raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)
            _logger.debug(
                "Timeout acquiring semaphore '%s' (instance: %s, count: %s)",
                self.key,
                self.instance_id,
                current_count,
            )
            return False

        _logger.debug(
            "Failed to acquire semaphore '%s' - %s (count: %s)",
            self.key,
            status,
            current_count,
        )
        raise SemaphoreAcquisitionError(name=self.key, capacity=self.capacity)

    async def release(self) -> None:
        """
        Release the semaphore atomically using Lua script.

        Raises:
            SemaphoreNotAcquiredError: If semaphore was not acquired by this instance
        """

        # Execute the release Lua script atomically
        cls = type(self)
        assert cls.release_script is not None  # nosec
        result = await cls.release_script(  # pylint: disable=not-callable
            keys=[self.tokens_key, self.holders_key, self.holder_key],
            args=[self.instance_id],
            client=self.redis_client.redis,
        )

        assert isinstance(result, list)  # nosec
        exit_code, status, current_count = result
        if exit_code == SCRIPT_OK_EXIT_CODE:
            assert status == "released"  # nosec
            _logger.debug(
                "Released semaphore '%s' (instance: %s, count: %s)",
                self.key,
                self.instance_id,
                current_count,
            )
            return

        # Instance was already expired or not acquired
        assert exit_code == SCRIPT_BAD_EXIT_CODE  # nosec
        _logger.error(
            "Failed to release semaphore '%s' - %s (instance: %s, count: %s)",
            self.key,
            status,
            self.instance_id,
            current_count,
        )
        raise SemaphoreNotAcquiredError(name=self.key)

    async def reacquire(self) -> None:
        """
        Atomically renew a semaphore entry using Lua script.

        This function is intended to be called by decorators or external renewal mechanisms.


        Raises:
            SemaphoreLostError: If the semaphore was lost or expired
        """

        ttl_seconds = int(self.ttl.total_seconds())

        # Execute the renewal Lua script atomically
        cls = type(self)
        assert cls.renew_script is not None  # nosec
        result = await cls.renew_script(  # pylint: disable=not-callable
            keys=[self.holders_key, self.holder_key],
            args=[self.instance_id, ttl_seconds],
            client=self.redis_client.redis,
        )

        assert isinstance(result, list)  # nosec
        exit_code, status, current_count = result

        if exit_code == SCRIPT_OK_EXIT_CODE:
            assert status == "renewed"  # nosec
            _logger.debug(
                "Renewed semaphore '%s' (instance: %s, count: %s)",
                self.key,
                self.instance_id,
                current_count,
            )
            return
        assert exit_code == SCRIPT_BAD_EXIT_CODE  # nosec

        _logger.warning(
            "Semaphore '%s' holder key was lost (instance: %s, status: %s, count: %s)",
            self.key,
            self.instance_id,
            status,
            current_count,
        )

        raise SemaphoreLostError(name=self.key, instance_id=self.instance_id)

    async def is_acquired(self) -> bool:
        """Check if the semaphore is currently acquired by this instance."""
        return (
            await handle_redis_returns_union_types(
                self.redis_client.redis.exists(self.holder_key)
            )
            == 1
        )

    async def get_current_count(self) -> int:
        """Get the current number of semaphore holders"""
        return await handle_redis_returns_union_types(
            self.redis_client.redis.scard(self.holders_key)
        )

    async def get_available_count(self) -> int:
        """Get the number of available semaphore slots"""
        await self._initialize_semaphore()
        return await handle_redis_returns_union_types(
            self.redis_client.redis.llen(self.tokens_key)
        )

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
