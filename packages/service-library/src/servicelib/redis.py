import contextlib
import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Final

import redis.asyncio as aioredis
import redis.exceptions
from pydantic import NonNegativeFloat
from pydantic.errors import PydanticErrorMixin
from redis.asyncio.lock import Lock
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .background_task import periodic_task
from .logging_utils import log_catch

_DEFAULT_LOCK_TTL: datetime.timedelta = datetime.timedelta(seconds=10)

_MINUTE: Final[NonNegativeFloat] = 60
_WAIT_SECS: Final[NonNegativeFloat] = 2

logger = logging.getLogger(__name__)


def _get_lock_renew_interval() -> datetime.timedelta:
    return _DEFAULT_LOCK_TTL * 0.6


class CouldNotAcquireLockError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Lock {lock.name} could not be acquired!"


@dataclass
class RedisClientSDK:
    redis_dsn: str
    _client: aioredis.Redis = field(init=False)

    @property
    def redis(self) -> aioredis.Redis:
        return self._client

    def __post_init__(self):
        # Run 3 retries with exponential backoff strategy source: https://redis.readthedocs.io/en/stable/backoff.html
        retry = Retry(ExponentialBackoff(cap=0.512, base=0.008), retries=3)
        self._client = aioredis.from_url(
            self.redis_dsn,
            retry=retry,
            retry_on_error=[
                redis.exceptions.BusyLoadingError,
                redis.exceptions.ConnectionError,
                redis.exceptions.TimeoutError,
            ],
            encoding="utf-8",
            decode_responses=True,
        )

    async def setup(self) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(1 * _MINUTE),
            wait=wait_fixed(_WAIT_SECS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                if not await self._client.ping():
                    await self._client.close(close_connection_pool=True)
                    raise ConnectionError(f"Connection to {self.redis_dsn!r} failed")
                logger.info(
                    "Connection to %s succeeded with %s [%s]",
                    f"redis at {self.redis_dsn=}",
                    f"{self._client=}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
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
        """
        Tries to acquire the lock, if locked raises CouldNotAcquireLockError

        When `blocking` is True, waits `blocking_timeout_s` for the lock to be
        acquired, otherwise raises `CouldNotAcquireLockError`
        """

        ttl_lock = None
        try:

            async def _auto_extend_lock(lock: Lock) -> None:
                await lock.reacquire()

            ttl_lock = self._client.lock(
                lock_key, timeout=_DEFAULT_LOCK_TTL.total_seconds()
            )

            if not await ttl_lock.acquire(
                blocking=blocking, token=lock_value, blocking_timeout=blocking_timeout_s
            ):
                # NOTE: a lot of things can go wrong when trying to acquire the lock:
                # - the lock can be already in use
                # - redis can be temporarily unavailable
                # - networking can be slow
                raise CouldNotAcquireLockError(lock=ttl_lock)

            async with periodic_task(
                _auto_extend_lock,
                interval=_get_lock_renew_interval(),
                task_name=f"{lock_key}_auto_extend",
                lock=ttl_lock,
            ):
                yield ttl_lock

        finally:
            if ttl_lock:
                with log_catch(logger, reraise=False):
                    await ttl_lock.release()

    async def lock_value(self, lock_name: str) -> str | None:
        return await self._client.get(lock_name)


@dataclass
class RedisClientsManager:
    """
    Manages the lifetime of redis client sdk connections
    """

    databases: set[RedisDatabase]
    settings: RedisSettings

    _client_sdks: dict[RedisDatabase:RedisClientSDK] = field(default_factory=dict)

    async def setup(self) -> None:
        for db in self.databases:
            self._client_sdks[db] = client_sdk = RedisClientSDK(
                redis_dsn=self.settings.build_redis_dsn(db)
            )
            await client_sdk.setup()

    async def shutdown(self) -> None:
        client_sdk: RedisClientSDK
        for client_sdk in self._client_sdks.values():
            await client_sdk.shutdown()

    def client(self, database: RedisDatabase) -> RedisClientSDK:
        return self._client_sdks[database]
