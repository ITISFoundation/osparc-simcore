import contextlib
import datetime
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Final, Optional, Union

import redis.asyncio as aioredis
import redis.exceptions
from pydantic.errors import PydanticErrorMixin
from redis.asyncio.lock import Lock
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from .background_task import periodic_task
from .logging_utils import log_catch

_DEFAULT_LOCK_TTL: Final[datetime.timedelta] = datetime.timedelta(seconds=10)
_AUTO_EXTEND_LOCK_RATIO: Final[float] = 0.6

logger = logging.getLogger(__name__)


class AlreadyLockedError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Lock {lock.name} is already locked!"


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

    async def close(self) -> None:
        await self._client.close(close_connection_pool=True)

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except ConnectionError:
            return False

    @contextlib.asynccontextmanager
    async def lock_context(
        self,
        lock_key: str,
        lock_value: Optional[Union[bytes, str]] = None,
    ) -> AsyncIterator[Lock]:
        ttl_lock = None
        try:

            async def _auto_extend_lock(lock: Lock) -> None:
                await lock.reacquire()

            ttl_lock = self._client.lock(
                lock_key, timeout=_DEFAULT_LOCK_TTL.total_seconds()
            )
            if not await ttl_lock.acquire(blocking=False, token=lock_value):
                raise AlreadyLockedError(lock=ttl_lock)
            async with periodic_task(
                _auto_extend_lock,
                interval=_AUTO_EXTEND_LOCK_RATIO * _DEFAULT_LOCK_TTL,
                task_name=f"{lock_key}_auto_extend",
                lock=ttl_lock,
            ):
                yield ttl_lock

        finally:
            if ttl_lock:
                with log_catch(logger, reraise=False):
                    await ttl_lock.release()

    async def is_locked(self, lock_name: str) -> bool:
        lock = self._client.lock(lock_name)
        return await lock.locked()

    async def lock_value(self, lock_name: str) -> Optional[str]:
        return await self._client.get(lock_name)
