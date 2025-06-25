import asyncio
import datetime
import logging
from asyncio import Task
from dataclasses import dataclass, field
from typing import Final
from uuid import uuid4

import redis.asyncio as aioredis
import redis.exceptions
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
    DEFAULT_SOCKET_TIMEOUT,
)

_logger = logging.getLogger(__name__)

# SEE https://github.com/ITISFoundation/osparc-simcore/pull/7077
_HEALTHCHECK_TASK_TIMEOUT_S: Final[float] = 3.0


@dataclass
class RedisClientSDK:
    redis_dsn: str
    client_name: str
    decode_responses: bool = DEFAULT_DECODE_RESPONSES
    health_check_interval: datetime.timedelta = DEFAULT_HEALTH_CHECK_INTERVAL

    _client: aioredis.Redis = field(init=False)
    _health_check_task: Task | None = None
    _health_check_task_started_event: asyncio.Event | None = None
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
            socket_timeout=DEFAULT_SOCKET_TIMEOUT.total_seconds(),
            encoding="utf-8",
            decode_responses=self.decode_responses,
            client_name=self.client_name,
        )
        # NOTE: connection is done here already
        self._is_healthy = False
        self._health_check_task_started_event = asyncio.Event()

        @periodic(interval=self.health_check_interval)
        async def _periodic_check_health() -> None:
            assert self._health_check_task_started_event  # nosec
            self._health_check_task_started_event.set()
            self._is_healthy = await self.ping()

        self._health_check_task = asyncio.create_task(
            _periodic_check_health(),
            name=f"redis_service_health_check_{self.redis_dsn}__{uuid4()}",
        )

        _logger.info(
            "Connection to %s succeeded with %s",
            f"redis at {self.redis_dsn=}",
            f"{self._client=}",
        )

    async def shutdown(self) -> None:
        with log_context(
            _logger, level=logging.DEBUG, msg=f"Shutdown RedisClientSDK {self}"
        ):
            if self._health_check_task:
                assert self._health_check_task_started_event  # nosec
                # NOTE: wait for the health check task to have started once before we can cancel it
                await self._health_check_task_started_event.wait()
                await cancel_wait_task(
                    self._health_check_task, max_delay=_HEALTHCHECK_TASK_TIMEOUT_S
                )

            await self._client.aclose(close_connection_pool=True)

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            # NOTE: retry_* input parameters from aioredis.from_url do not apply for the ping call
            await self._client.ping()
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
