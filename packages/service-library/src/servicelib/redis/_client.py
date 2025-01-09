import asyncio
import datetime
import logging
from asyncio import Task
from dataclasses import dataclass, field
from uuid import uuid4

import redis.asyncio as aioredis
import redis.exceptions
from redis.asyncio.lock import Lock
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from servicelib.async_utils import cancel_wait_task
from tenacity import retry
from yarl import URL

from ..logging_utils import log_catch
from ..retry_policies import RedisRetryPolicyUponInitialization
from ._constants import (
    DEFAULT_DECODE_RESPONSES,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_LOCK_TTL,
    DEFAULT_SOCKET_TIMEOUT,
    SHUTDOWN_TIMEOUT_S,
)
from ._errors import CouldNotConnectToRedisError

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

    def __post_init__(self) -> None:
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
            await cancel_wait_task(
                self._health_check_task, max_delay=SHUTDOWN_TIMEOUT_S
            )
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
