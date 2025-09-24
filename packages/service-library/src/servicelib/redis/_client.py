import asyncio
import datetime
import logging
from asyncio import Task
from dataclasses import dataclass, field
from typing import Final
from uuid import uuid4

import redis.asyncio as aioredis
import redis.exceptions
import tenacity
from common_library.async_tools import cancel_wait_task
from redis.asyncio.lock import Lock
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from ..background_task import periodic
from ..logging_utils import log_catch, log_context
from ._constants import (
    DEFAULT_DECODE_RESPONSES,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_LOCK_TTL,
)

_logger = logging.getLogger(__name__)

_HEALTHCHECK_TIMEOUT_S: Final[float] = 3.0


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_delay(20),
    before_sleep=tenacity.before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
async def wait_till_redis_is_responsive(client: aioredis.Redis) -> None:
    if not await client.ping():
        raise tenacity.TryAgain


@dataclass
class RedisClientSDK:
    redis_dsn: str
    client_name: str
    decode_responses: bool = DEFAULT_DECODE_RESPONSES
    health_check_interval: datetime.timedelta = DEFAULT_HEALTH_CHECK_INTERVAL

    _client: aioredis.Redis = field(init=False)
    _task_health_check: Task | None = None
    _started_event_task_health_check: asyncio.Event | None = None
    _cancelled_event_task_health_check: asyncio.Event | None = None
    _is_healthy: bool = False

    @property
    def redis(self) -> aioredis.Redis:
        return self._client

    def __post_init__(self) -> None:
        self._client = aioredis.from_url(
            self.redis_dsn,
            # Run 3 retries with exponential backoff strategy source: https://redis.readthedocs.io/en/stable/backoff.html
            retry=Retry(ExponentialBackoff(cap=0.512, base=0.008), retries=3),
            retry_on_error=[
                redis.exceptions.BusyLoadingError,
                redis.exceptions.ConnectionError,
            ],
            retry_on_timeout=True,
            socket_timeout=None,  # NOTE: setting a timeout here can lead to issues with long running commands
            encoding="utf-8",
            decode_responses=self.decode_responses,
            client_name=self.client_name,
        )
        self._is_healthy = False
        self._started_event_task_health_check = asyncio.Event()
        self._cancelled_event_task_health_check = asyncio.Event()

    async def setup(self) -> None:
        @periodic(interval=self.health_check_interval)
        async def _periodic_check_health() -> None:
            assert self._started_event_task_health_check  # nosec
            assert self._cancelled_event_task_health_check  # nosec
            self._started_event_task_health_check.set()
            self._is_healthy = await self.ping()
            if self._cancelled_event_task_health_check.is_set():
                raise asyncio.CancelledError

        self._task_health_check = asyncio.create_task(
            _periodic_check_health(),
            name=f"redis_service_health_check_{self.redis_dsn}__{uuid4()}",
        )

        await wait_till_redis_is_responsive(self._client)

        _logger.info(
            "Connection to %s succeeded with %s",
            f"redis at {self.redis_dsn=}",
            f"{self._client=}",
        )

    async def shutdown(self) -> None:
        with log_context(
            _logger, level=logging.DEBUG, msg=f"Shutdown RedisClientSDK {self}"
        ):
            if self._task_health_check:
                assert self._started_event_task_health_check  # nosec
                await self._started_event_task_health_check.wait()
                assert self._cancelled_event_task_health_check  # nosec
                self._cancelled_event_task_health_check.set()
                await cancel_wait_task(self._task_health_check, max_delay=None)

            await self._client.aclose(close_connection_pool=True)

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            # NOTE: retry_* input parameters from aioredis.from_url do not apply for the ping call
            await asyncio.wait_for(self._client.ping(), timeout=_HEALTHCHECK_TIMEOUT_S)
            return True

        return False

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

    def create_lock(
        self, lock_name: str, *, ttl: datetime.timedelta | None = DEFAULT_LOCK_TTL
    ) -> Lock:
        return self._client.lock(
            name=lock_name,
            timeout=ttl.total_seconds() if ttl is not None else None,
            blocking=False,
        )

    async def lock_value(self, lock_name: str) -> str | None:
        output: str | None = await self._client.get(lock_name)
        return output
