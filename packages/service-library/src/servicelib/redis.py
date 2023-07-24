import contextlib
import datetime
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Final
from uuid import uuid4

import redis.asyncio as aioredis
import redis.exceptions
from pydantic import NonNegativeFloat
from pydantic.errors import PydanticErrorMixin
from redis.asyncio.lock import Lock
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from servicelib.retry_policies import RedisRetryPolicyUponInitialization
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity import retry

from .background_task import periodic_task
from .logging_utils import log_catch, log_context

_DEFAULT_LOCK_TTL: Final[datetime.timedelta] = datetime.timedelta(seconds=10)
_CANCEL_TASK_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=0.1)
_MINUTE: Final[NonNegativeFloat] = 60
_WAIT_SECS: Final[NonNegativeFloat] = 1


logger = logging.getLogger(__name__)


class BaseRedisError(PydanticErrorMixin, RuntimeError):
    ...


class CouldNotAcquireLockError(BaseRedisError):
    msg_template: str = "Lock {lock.name} could not be acquired!"


class CouldNotConnectToRedisError(BaseRedisError):
    msg_template: str = "Connection to '{dsn}' failed"


@dataclass
class RedisClientSDK:
    redis_dsn: str
    _client: aioredis.Redis = field(init=False)

    @property
    def redis(self) -> aioredis.Redis:
        return self._client

    def __post_init__(self):
        self._client = aioredis.from_url(
            self.redis_dsn,
            # Run 3 retries with exponential backoff strategy source: https://redis.readthedocs.io/en/stable/backoff.html
            retry=Retry(ExponentialBackoff(cap=0.512, base=0.008), retries=3),
            retry_on_error=[
                redis.exceptions.BusyLoadingError,
                redis.exceptions.ConnectionError,
                redis.exceptions.TimeoutError,
            ],
            encoding="utf-8",
            decode_responses=True,
        )

    @retry(**RedisRetryPolicyUponInitialization(logger).kwargs)
    async def setup(self) -> None:
        if not await self._client.ping():
            await self.shutdown()
            raise CouldNotConnectToRedisError(dsn=self.redis_dsn)
        logger.info(
            "Connection to %s succeeded with %s",
            f"redis at {self.redis_dsn=}",
            f"{self._client=}",
        )

    async def shutdown(self) -> None:
        await self._client.close(close_connection_pool=True)

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except redis.exceptions.ConnectionError:
            return False

    @contextlib.asynccontextmanager
    async def lock_context(
        self,
        lock_key: str,
        lock_value: bytes | str | None = None,
        *,
        blocking: bool = False,
        blocking_timeout_s: NonNegativeFloat = 5,
    ) -> AsyncIterator[Lock]:
        """Tries to acquire a lock.

        :param lock_key: unique name of the lock
        :param lock_value: content of the lock, defaults to None
        :param blocking: should block here while acquiring the lock, defaults to False
        :param blocking_timeout_s: time to wait while acquire a lock before giving up, defaults to 5

        :raises CouldNotAcquireLockError: reasons why lock acquisition fails:
            1. `blocking==False` the lock was already acquired by some other entity
            2. `blocking==True` timeouts out while waiting for lock to be free (another entity holds the lock)
        """

        total_lock_duration: datetime.timedelta = _DEFAULT_LOCK_TTL
        lock_unique_id = f"lock_extender_{lock_key}_{uuid4()}"

        ttl_lock: Lock = self._client.lock(
            name=lock_key,
            timeout=total_lock_duration.total_seconds(),
            blocking=blocking,
            blocking_timeout=blocking_timeout_s,
        )

        if not await ttl_lock.acquire(token=lock_value):
            raise CouldNotAcquireLockError(lock=ttl_lock)

        async def _extend_lock(lock: Lock) -> None:
            with log_context(
                logger, logging.DEBUG, f"Extending lock {lock_unique_id}"
            ), log_catch(logger, reraise=False):
                await lock.reacquire()

        try:
            async with periodic_task(
                _extend_lock,
                interval=total_lock_duration / 2,
                task_name=lock_unique_id,
                lock=ttl_lock,
                stop_timeout=0.1,
            ):
                # lock is in use now
                yield ttl_lock
        finally:
            # NOTE Why is this error suppressed? Given the following situation:
            # - 250 locks are acquire in parallel with the option `blocking=True`,
            #     meaning: it will wait for the lock to be free before acquiring it
            # - when the lock is acquired the `_extend_lock` task is started
            #     in the background, extending the lock at a fixed interval of time,
            #     which is half of the duration of the lock's TTL
            # - before the task is released the lock extension task is cancelled
            # Here is where the issue occurs:
            # - some time passes between the task's cancellation and
            #     the call to release the lock
            # - if the TTL is too small, 1/2 of the TTL might be just shorter than
            #     the time it passes to between the task is canceled and the task lock is released
            # - this means that the lock will expire and be considered as not owned any longer
            # For example: in one of the failing tests the TTL is set to `0.25` seconds,
            # and half of that is `0.125` seconds.

            # Above implies that only one "task" `owns` and `extends` the lock at a time.
            # The issue appears to be related some timings (being too low).
            try:
                await ttl_lock.release()
            except redis.exceptions.LockNotOwnedError:
                # if this appears outside tests it can cause issues since something might be happening
                logger.warning(
                    "Attention: lock is no longer owned. This is unexpected and requires investigation"
                )

    async def lock_value(self, lock_name: str) -> str | None:
        output: str | None = await self._client.get(lock_name)
        return output


@dataclass
class RedisClientsManager:
    """
    Manages the lifetime of redis client sdk connections
    """

    databases: set[RedisDatabase]
    settings: RedisSettings

    _client_sdks: dict[RedisDatabase, RedisClientSDK] = field(default_factory=dict)

    async def setup(self) -> None:
        for db in self.databases:
            self._client_sdks[db] = client_sdk = RedisClientSDK(
                redis_dsn=self.settings.build_redis_dsn(db)
            )
            await client_sdk.setup()

    async def shutdown(self) -> None:
        await logged_gather(*(c.shutdown() for c in self._client_sdks.values()))

    def client(self, database: RedisDatabase) -> RedisClientSDK:
        return self._client_sdks[database]
