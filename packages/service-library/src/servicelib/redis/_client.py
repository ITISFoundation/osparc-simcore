import asyncio
import contextlib
import datetime
import logging
from asyncio import Task
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import uuid4

import redis.asyncio as aioredis
import redis.exceptions
from pydantic import NonNegativeFloat
from redis.asyncio.lock import Lock
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from tenacity import retry
from yarl import URL

from ..background_task import periodic_task
from ..logging_utils import log_catch
from ..retry_policies import RedisRetryPolicyUponInitialization
from ._constants import (
    DEFAULT_DECODE_RESPONSES,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_LOCK_TTL,
    DEFAULT_SOCKET_TIMEOUT,
)
from ._errors import CouldNotAcquireLockError, CouldNotConnectToRedisError
from ._utils import auto_extend_lock, cancel_or_warn

_logger = logging.getLogger(__name__)


@dataclass
class RedisClientSDK:
    redis_dsn: str
    client_name: str
    decode_responses: bool = DEFAULT_DECODE_RESPONSES
    health_check_interval: datetime.timedelta = DEFAULT_HEALTH_CHECK_INTERVAL

    _client: aioredis.Redis = field(init=False)
    _health_check_task: Task | None = None
    _is_healthy: bool = False
    _continue_health_checking: bool = True

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
            socket_timeout=DEFAULT_SOCKET_TIMEOUT.total_seconds(),
            socket_connect_timeout=DEFAULT_SOCKET_TIMEOUT.total_seconds(),
            encoding="utf-8",
            decode_responses=self.decode_responses,
            client_name=self.client_name,
        )

    @retry(**RedisRetryPolicyUponInitialization(_logger).kwargs)
    async def setup(self) -> None:
        if not await self.ping():
            await self.shutdown()
            url_safe: URL = URL(self.redis_dsn).with_password("???")
            raise CouldNotConnectToRedisError(dsn=f"{url_safe}")

        self._health_check_task = asyncio.create_task(
            self._check_health(),
            name=f"redis_service_health_check_{self.redis_dsn}__{uuid4()}",
        )
        self._is_healthy = True

        _logger.info(
            "Connection to %s succeeded with %s",
            f"redis at {self.redis_dsn=}",
            f"{self._client=}",
        )

    async def shutdown(self) -> None:
        if self._health_check_task:
            self._continue_health_checking = False
            await cancel_or_warn(self._health_check_task)
            self._health_check_task = None

        await self._client.aclose(close_connection_pool=True)

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            await self._client.ping()
            return True
        return False

    async def _check_health(self) -> None:
        sleep_s = self.health_check_interval.total_seconds()

        while self._continue_health_checking:
            with log_catch(_logger, reraise=False):
                self._is_healthy = await self.ping()
            await asyncio.sleep(sleep_s)

    @property
    def is_healthy(self) -> bool:
        """Returns the result of the last health check.
        If redis becomes available, after being not available,
        it will once more return ``True``

        Returns:
            ``False``: if the service is no longer reachable
            ``True``: when service is reachable
        """
        return self._is_healthy

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

        total_lock_duration: datetime.timedelta = DEFAULT_LOCK_TTL
        lock_unique_id = f"lock_extender_{lock_key}_{uuid4()}"

        ttl_lock: Lock = self._client.lock(
            name=lock_key,
            timeout=total_lock_duration.total_seconds(),
            blocking=blocking,
            blocking_timeout=blocking_timeout_s,
        )

        if not await ttl_lock.acquire(token=lock_value):
            raise CouldNotAcquireLockError(lock=ttl_lock)

        try:
            async with periodic_task(
                auto_extend_lock,
                interval=total_lock_duration / 2,
                task_name=lock_unique_id,
                lock=ttl_lock,
                stop_timeout=0.1,
            ):
                # lock is in use now
                yield ttl_lock
        finally:
            # NOTE Why is this error suppressed? Given the following situation:
            # - 250 locks are acquired in parallel with the option `blocking=True`,
            #     meaning: it will wait for the lock to be free before acquiring it
            # - when the lock is acquired the `_extend_lock` task is started
            #     in the background, extending the lock at a fixed interval of time,
            #     which is half of the duration of the lock's TTL.
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
                _logger.warning(
                    "Attention: lock is no longer owned. This is unexpected and requires investigation"
                )

    async def lock_value(self, lock_name: str) -> str | None:
        output: str | None = await self._client.get(lock_name)
        return output
