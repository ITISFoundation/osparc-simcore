import asyncio
import logging
from asyncio import Task
from datetime import timedelta
from typing import Final
from uuid import uuid4

import tenacity
from common_library.async_tools import cancel_wait_task
from servicelib.background_task import periodic
from servicelib.logging_utils import log_catch, log_context
from temporalio.client import Client

_logger = logging.getLogger(__name__)

_HEALTHCHECK_TIMEOUT: Final[timedelta] = timedelta(seconds=3)
_HEALTHCHECK_INTERVAL: Final[timedelta] = timedelta(seconds=5)


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_delay(120),
    before_sleep=tenacity.before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
async def wait_till_temporalio_is_responsive(client: Client) -> None:
    if not await client.service_client.check_health(timeout=timedelta(seconds=5)):
        raise tenacity.TryAgain


class TemporalHealthCheck:
    def __init__(self, client: Client) -> None:
        self._client = client
        self._is_healthy: bool = False
        self._task_health_check: Task | None = None
        self._started_event: asyncio.Event = asyncio.Event()
        self._cancelled_event: asyncio.Event = asyncio.Event()

    @property
    def is_healthy(self) -> bool:
        return self._is_healthy

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            return await self._client.service_client.check_health(timeout=_HEALTHCHECK_TIMEOUT)
        return False

    async def setup(self) -> None:
        @periodic(interval=_HEALTHCHECK_INTERVAL)
        async def _periodic_check_health() -> None:
            self._started_event.set()
            self._is_healthy = await self.ping()
            if self._cancelled_event.is_set():
                raise asyncio.CancelledError

        self._task_health_check = asyncio.create_task(
            _periodic_check_health(),
            name=f"temporalio_health_check__{uuid4()}",
        )

        _logger.info("Temporalio health check started")

    async def shutdown(self) -> None:
        with log_context(_logger, level=logging.DEBUG, msg="Shutdown TemporalHealthCheck"):
            if self._task_health_check:
                await self._started_event.wait()
                self._cancelled_event.set()
                await cancel_wait_task(self._task_health_check, max_delay=None)
