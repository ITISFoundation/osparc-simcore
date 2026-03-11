import asyncio
import contextlib
import datetime
import logging
import socket
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, ClassVar

import arrow
import redis.exceptions
from common_library.async_tools import cancel_wait_task
from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    computed_field,
    field_validator,
)
from redis.commands.core import AsyncScript
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_random_exponential,
)

from ..background_task import periodic
from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
    DEFAULT_SEMAPHORE_TTL,
    SEMAPHORE_KEY_PREFIX,
)
from ._errors import (
    SemaphoreAcquisitionError,
    SemaphoreError,
    SemaphoreLostError,
    SemaphoreNotAcquiredError,
)
from ._semaphore_lua import (
    ACQUIRE_SEMAPHORE_SCRIPT,
    REGISTER_SEMAPHORE_TOKEN_SCRIPT,
    RELEASE_SEMAPHORE_SCRIPT,
    RENEW_SEMAPHORE_SCRIPT,
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
    key: Annotated[str, Field(min_length=1, description="Unique identifier for the semaphore")]
    capacity: Annotated[PositiveInt, Field(description="Maximum number of concurrent holders")]
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL
    blocking: Annotated[bool, Field(description="Whether acquire() should block until available")] = True
    blocking_timeout: Annotated[
        datetime.timedelta | None,
        Field(description="Maximum time to wait when blocking"),
    ] = None
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
    release_script: ClassVar[AsyncScript | None] = None
    renew_script: ClassVar[AsyncScript | None] = None

    _token: str | None = None  # currently held token, if any

    @classmethod
    def _register_scripts(cls, redis_client: RedisClientSDK) -> None:
        """Register Lua scripts with Redis if not already done.
        This is done once per class, not per instance. Internally the Redis client
        caches the script SHA, so this is efficient. Even if called multiple times,
        the script is only registered once."""
        if cls.acquire_script is None:
            cls.register_semaphore = redis_client.redis.register_script(REGISTER_SEMAPHORE_TOKEN_SCRIPT)
            cls.acquire_script = redis_client.redis.register_script(ACQUIRE_SEMAPHORE_SCRIPT)
            cls.release_script = redis_client.redis.register_script(RELEASE_SEMAPHORE_SCRIPT)
            cls.renew_script = redis_client.redis.register_script(RENEW_SEMAPHORE_SCRIPT)

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self.__class__._register_scripts(self.redis_client)  # noqa: SLF001

    @computed_field  # type: ignore[prop-decorator]
    @property
    def semaphore_key(self) -> str:
        """Redis key for the semaphore sorted set."""
        return f"{SEMAPHORE_KEY_PREFIX}{self.key}_cap{self.capacity}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tokens_key(self) -> str:
        """Redis key for the token pool LIST."""
        return f"{self.semaphore_key}:tokens"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holders_set(self) -> str:
        """Redis key for the holders SET."""
        return f"{self.semaphore_key}:holders_set"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holder_key(self) -> str:
        """Redis key for this instance's holder entry."""
        return f"{self.semaphore_key}:holders:{self.instance_id}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holders_set_ttl(self) -> datetime.timedelta:
        """TTL for the holders SET"""
        return self.ttl * 5

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tokens_set_ttl(self) -> datetime.timedelta:
        """TTL for the tokens SET"""
        return self.ttl * 5

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: datetime.timedelta) -> datetime.timedelta:
        if v.total_seconds() < 1:
            msg = "TTL must be positive"
            raise ValueError(msg)
        return v

    @field_validator("blocking_timeout")
    @classmethod
    def validate_timeout(cls, v: datetime.timedelta | None) -> datetime.timedelta | None:
        if v is not None and v.total_seconds() <= 0:
            msg = "Timeout must be positive"
            raise ValueError(msg)
        return v

    async def _ensure_semaphore_initialized(self) -> None:
        """Initializes the semaphore in Redis if not already done."""
        assert self.register_semaphore is not None  # nosec
        result = await self.register_semaphore(  # pylint: disable=not-callable
            keys=[self.tokens_key, self.holders_set],
            args=[self.capacity, self.holders_set_ttl.total_seconds()],
            client=self.redis_client.redis,
        )
        assert isinstance(result, list)  # nosec
        exit_code, status = result
        assert exit_code == SCRIPT_OK_EXIT_CODE  # nosec
        _logger.debug("Semaphore '%s' init status: %s", self.key, status)

    async def _blocking_acquire(self) -> str | None:
        @retry(
            wait=wait_random_exponential(min=0.1, max=0.5),
            retry=retry_if_exception_type(redis.exceptions.TimeoutError),
        )
        async def _acquire_forever_on_socket_timeout() -> list[str] | None:
            # NOTE: brpop returns None on timeout

            tokens_key_token: list[str] | None = await handle_redis_returns_union_types(
                self.redis_client.redis.brpop(
                    [self.tokens_key],
                    timeout=None,  # NOTE: we always block forever since tenacity takes care of timing out
                )
            )
            return tokens_key_token

        try:
            # NOTE: redis-py library timeouts when the defined socket timeout triggers
            # The BRPOP command itself could timeout but the redis-py socket timeout defeats the purpose
            # so we always block forever on BRPOP, tenacity takes care of retrying when a socket timeout happens
            # and we use asyncio.timeout to enforce the blocking_timeout if defined
            async with asyncio.timeout(self.blocking_timeout.total_seconds() if self.blocking_timeout else None):
                tokens_key_token = await _acquire_forever_on_socket_timeout()
            assert tokens_key_token is not None  # nosec
            assert len(tokens_key_token) == 2  # nosec  # noqa: PLR2004
            assert tokens_key_token[0] == self.tokens_key  # nosec
            return tokens_key_token[1]
        except TimeoutError as e:
            raise SemaphoreAcquisitionError(name=self.key, instance_id=self.instance_id) from e

    async def _non_blocking_acquire(self) -> str | None:
        token: str | list[str] | None = await handle_redis_returns_union_types(
            self.redis_client.redis.rpop(self.tokens_key)
        )
        if token is None:
            _logger.debug(
                "Semaphore '%s' not acquired (no tokens available) (instance: %s)",
                self.key,
                self.instance_id,
            )
            return None

        assert isinstance(token, str)  # nosec
        return token

    async def acquire(self) -> bool:
        """
        Acquire the semaphore.

        Returns:
            True if acquired successfully, False if not acquired and non-blocking

        Raises:
            SemaphoreAcquisitionError: If acquisition fails and blocking=True
        """
        await self._ensure_semaphore_initialized()

        if await self.is_acquired():
            _logger.debug(
                "Semaphore '%s' already acquired by this instance (instance: %s)",
                self.key,
                self.instance_id,
            )
            return True

        if self.blocking is False:
            self._token = await self._non_blocking_acquire()
            if not self._token:
                return False
        else:
            self._token = await self._blocking_acquire()

        assert self._token is not None  # nosec
        # set up the semaphore holder with a TTL
        assert self.acquire_script is not None  # nosec
        result = await self.acquire_script(  # pylint: disable=not-callable
            keys=[self.holders_set, self.holder_key],
            args=[
                self._token,
                self.instance_id,
                self.ttl.total_seconds(),
                self.holders_set_ttl.total_seconds(),
            ],
            client=self.redis_client.redis,
        )

        # Lua script returns: [exit_code, status, current_count, expired_count]
        assert isinstance(result, list)  # nosec
        exit_code, status, token, current_count = result

        assert exit_code == SCRIPT_OK_EXIT_CODE  # nosec
        assert status == "acquired"  # nosec

        _logger.debug(
            "Acquired semaphore '%s' with token %s (instance: %s, count: %s)",
            self.key,
            token,
            self.instance_id,
            current_count,
        )
        return True

    async def release(self) -> None:
        """
        Release the semaphore

        Raises:
            SemaphoreNotAcquiredError: If semaphore was not acquired by this instance
        """

        # Execute the release Lua script atomically
        assert self.release_script is not None  # nosec
        release_args = [self.instance_id]
        if self._token is not None:
            release_args.append(self._token)
        result = await self.release_script(  # pylint: disable=not-callable
            keys=[self.tokens_key, self.holders_set, self.holder_key],
            args=release_args,
            client=self.redis_client.redis,
        )
        self._token = None

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
        if status == "not_held":
            raise SemaphoreNotAcquiredError(name=self.key, instance_id=self.instance_id)
        assert status == "expired"  # nosec
        raise SemaphoreLostError(name=self.key, instance_id=self.instance_id)

    async def reacquire(self) -> None:
        """
        Re-acquire a semaphore
        This function is intended to be called by decorators or external renewal mechanisms.


        Raises:
            SemaphoreLostError: If the semaphore was lost or expired
        """

        ttl_seconds = self.ttl.total_seconds()

        # Execute the renewal Lua script atomically
        assert self.renew_script is not None  # nosec
        result = await self.renew_script(  # pylint: disable=not-callable
            keys=[self.holders_set, self.holder_key, self.tokens_key],
            args=[
                self.instance_id,
                ttl_seconds,
                self.holders_set_ttl.total_seconds(),
                self.tokens_set_ttl.total_seconds(),
            ],
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
        if status == "not_held":
            raise SemaphoreNotAcquiredError(name=self.key, instance_id=self.instance_id)
        assert status == "expired"  # nosec
        raise SemaphoreLostError(name=self.key, instance_id=self.instance_id)

    async def is_acquired(self) -> bool:
        """Check if the semaphore is currently acquired by this instance."""
        return bool(await handle_redis_returns_union_types(self.redis_client.redis.exists(self.holder_key)) == 1)

    async def current_count(self) -> int:
        """Get the current number of semaphore holders"""
        return await handle_redis_returns_union_types(self.redis_client.redis.scard(self.holders_set))

    async def available_tokens(self) -> int:
        """Get the size of the semaphore (number of available tokens)"""
        await self._ensure_semaphore_initialized()
        return await handle_redis_returns_union_types(self.redis_client.redis.llen(self.tokens_key))


@contextlib.asynccontextmanager
async def distributed_semaphore(  # noqa: C901
    redis_client: RedisClientSDK,
    *,
    key: str,
    capacity: PositiveInt,
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    blocking: bool = True,
    blocking_timeout: datetime.timedelta | None = None,
    expected_lock_overall_time: datetime.timedelta = DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
) -> AsyncIterator[DistributedSemaphore]:
    """
    Async context manager for DistributedSemaphore.

    Example:
        async with distributed_semaphore(redis_client, "my_resource", capacity=3) as sem:
            # Only 3 instances can execute this block concurrently
            await do_limited_work()
    """
    semaphore = DistributedSemaphore(
        redis_client=redis_client,
        key=key,
        capacity=capacity,
        ttl=ttl,
        blocking=blocking,
        blocking_timeout=blocking_timeout,
    )

    @periodic(interval=semaphore.ttl / 3, raise_on_error=True)
    async def _periodic_reacquisition(
        semaphore: DistributedSemaphore,
        started: asyncio.Event,
        cancellation_event: asyncio.Event,
    ) -> None:
        if cancellation_event.is_set():
            raise asyncio.CancelledError
        if not started.is_set():
            started.set()
        await semaphore.reacquire()

    lock_acquisition_time = None
    try:
        if not await semaphore.acquire():
            raise SemaphoreAcquisitionError(name=key, instance_id=semaphore.instance_id)

        lock_acquisition_time = arrow.utcnow()

        async with (
            asyncio.TaskGroup() as tg
        ):  # NOTE: using task group ensures proper cancellation propagation of parent task
            auto_reacquisition_started = asyncio.Event()
            cancellation_event = asyncio.Event()
            auto_reacquisition_task = tg.create_task(
                _periodic_reacquisition(semaphore, auto_reacquisition_started, cancellation_event),
                name=f"semaphore/auto_reacquisition_task_{semaphore.key}_{semaphore.instance_id}",
            )
            await auto_reacquisition_started.wait()
            try:
                # NOTE: this try/finally ensures that cancellation_event is set when we exit the context
                # even in case of exceptions
                yield semaphore
            finally:
                cancellation_event.set()  # NOTE: this ensure cancellation is effective
                await cancel_wait_task(auto_reacquisition_task)
    except BaseExceptionGroup as eg:
        semaphore_errors, other_errors = eg.split(SemaphoreError)
        if other_errors:
            assert len(other_errors.exceptions) == 1  # nosec
            raise other_errors.exceptions[0] from eg
        assert semaphore_errors is not None  # nosec
        assert len(semaphore_errors.exceptions) == 1  # nosec
        raise semaphore_errors.exceptions[0] from eg
    finally:
        try:
            await semaphore.release()
        except SemaphoreNotAcquiredError as exc:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Unexpected error while releasing semaphore '{semaphore.key}'",
                    error=exc,
                    error_context={
                        "semaphore_key": semaphore.key,
                        "semaphore_instance_id": semaphore.instance_id,
                        "hostname": socket.gethostname(),
                    },
                    tip="This indicates a logic error in the code using the semaphore",
                )
            )
        except SemaphoreLostError as exc:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Unexpected error while releasing semaphore '{semaphore.key}'",
                    error=exc,
                    error_context={
                        "semaphore_key": semaphore.key,
                        "semaphore_instance_id": semaphore.instance_id,
                        "hostname": socket.gethostname(),
                    },
                    tip="This indicates that the semaphore was lost or expired before release. "
                    "Look for synchronouse code or the loop is very busy and cannot schedule the reacquisition task.",
                )
            )
        if lock_acquisition_time is not None:
            lock_release_time = arrow.utcnow()
            locking_time = lock_release_time - lock_acquisition_time
            if locking_time > expected_lock_overall_time:
                _logger.warning(
                    "Semaphore '%s' was held for %s by %s which is longer than expected (%s). "
                    "TIP: consider reducing the locking time by optimizing the code inside "
                    "the critical section or increasing the default locking time",
                    semaphore.key,
                    locking_time,
                    semaphore.instance_id,
                    expected_lock_overall_time,
                )
