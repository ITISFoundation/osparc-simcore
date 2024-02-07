import asyncio
import logging
from asyncio import Queue
from datetime import datetime, timezone
from typing import AsyncIterable, Awaitable, Callable, Final

from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pydantic import NonNegativeInt, ValidationError
from servicelib.rabbitmq import RabbitMQClient

from ..models.schemas.jobs import JobID, JobLog
from .director_v2 import DirectorV2Api

_logger = logging.getLogger(__name__)

_NEW_LINE: Final[str] = "\n"


class LogDistributionBaseException(Exception):
    pass


class LogStreamerNotRegistered(LogDistributionBaseException):
    pass


class LogStreamerRegistionConflict(LogDistributionBaseException):
    pass


class LogDistributor:
    def __init__(self, rabbitmq_client: RabbitMQClient):
        self._rabbit_client = rabbitmq_client
        self._log_streamers: dict[JobID, Callable[[JobLog], Awaitable[None]]] = {}
        self._queue_name: str

    async def setup(self):
        self._queue_name = await self._rabbit_client.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._distribute_logs,
            exclusive_queue=True,
            topics=[],
        )

    async def teardown(self):
        await self._rabbit_client.unsubscribe(self._queue_name)

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.teardown()

    async def _distribute_logs(self, data: bytes):
        try:
            got = LoggerRabbitMessage.parse_raw(
                data
            )  # rabbitmq client safe_nacks the message if this deserialization fails
        except ValidationError as e:
            _logger.debug(
                "Could not parse log message from RabbitMQ in LogDistributor._distribute_logs"
            )
            raise e
        _logger.debug(
            "LogDistributor._distribute_logs received message message from RabbitMQ: %s",
            got.json(),
        )
        item = JobLog(
            job_id=got.project_id,
            node_id=got.node_id,
            log_level=got.log_level,
            messages=got.messages,
        )
        callback = self._log_streamers.get(item.job_id)
        if callback is None:
            raise LogStreamerNotRegistered(
                f"Could not forward log because a logstreamer associated with job_id={item.job_id} was not registered"
            )
        await callback(item)
        return True

    async def register(
        self, job_id: JobID, callback: Callable[[JobLog], Awaitable[None]]
    ):
        if job_id in self._log_streamers:
            raise LogStreamerRegistionConflict(
                f"A stream was already connected to {job_id=}. Only a single stream can be connected at the time"
            )
        self._log_streamers[job_id] = callback
        await self._rabbit_client.add_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )

    async def deregister(self, job_id: JobID):
        if job_id not in self._log_streamers:
            raise LogStreamerNotRegistered(f"No stream was connected to {job_id=}.")
        await self._rabbit_client.remove_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )
        del self._log_streamers[job_id]


class LogStreamer:
    def __init__(
        self,
        *,
        user_id: UserID,
        director2_api: DirectorV2Api,
        job_id: JobID,
        log_distributor: LogDistributor,
        max_log_check_seconds: NonNegativeInt,
    ):
        self._user_id = user_id
        self._director2_api = director2_api
        self._queue: Queue[JobLog] = Queue()
        self._job_id: JobID = job_id
        self._log_distributor: LogDistributor = log_distributor
        self._is_registered: bool = False
        self._max_log_check_seconds: NonNegativeInt = max_log_check_seconds

    async def setup(self):
        await self._log_distributor.register(self._job_id, self._queue.put)
        self._is_registered = True

    async def teardown(self):
        await self._log_distributor.deregister(self._job_id)
        self._is_registered = False

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.teardown()

    async def _project_done(self) -> bool:
        task = await self._director2_api.get_computation(self._job_id, self._user_id)
        return not task.stopped is None

    async def log_generator(self) -> AsyncIterable[str]:
        if not self._is_registered:
            raise LogStreamerNotRegistered(
                f"LogStreamer for job_id={self._job_id} is not correctly registered"
            )
        last_log_time: datetime | None = None
        while True:
            while self._queue.empty():
                if await self._project_done():
                    return
                await asyncio.sleep(
                    0.2
                    if last_log_time is None
                    else min(
                        (datetime.now(tz=timezone.utc) - last_log_time).total_seconds(),
                        self._max_log_check_seconds,
                    )
                )
            log: JobLog = await self._queue.get()
            last_log_time = datetime.now(tz=timezone.utc)
            yield log.json() + _NEW_LINE
