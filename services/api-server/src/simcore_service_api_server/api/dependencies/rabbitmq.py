import asyncio
from asyncio.queues import Queue
from typing import Annotated, AsyncIterable, Awaitable, Callable, Final, cast

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from models_library.rabbitmq_messages import LoggerRabbitMessage
from pydantic import PositiveInt
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient

from ...models.schemas.jobs import JobID, JobLog
from ...services.director_v2 import DirectorV2Api
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client

_NEW_LINE: Final[str] = "\n"


def get_rabbitmq_client(app: Annotated[FastAPI, Depends(get_app)]) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_log_distributor(app: Annotated[FastAPI, Depends(get_app)]) -> "LogDistributor":
    assert app.state.log_distributor  # nosec
    return cast(LogDistributor, app.state.log_distributor)


class LogStreamingResponse(StreamingResponse):
    media_type = "application/x-ndjson"


class LogDistributor:
    _log_streamers: dict[JobID, Callable[[JobLog], Awaitable[None]]] = {}
    _rabbit_client: RabbitMQClient
    _queue_name: str

    def __init__(self, rabbitmq_client: RabbitMQClient):
        self._rabbit_client = rabbitmq_client

    async def setup(self):
        self._queue_name = await self._rabbit_client.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._distribute_logs,
            exclusive_queue=True,
            topics=[],
        )

    async def teardown(self):
        await self._rabbit_client.unsubscribe(self._queue_name)

    async def _distribute_logs(self, data: bytes):
        got = LoggerRabbitMessage.parse_raw(data)
        item = JobLog(
            job_id=got.project_id,
            node_id=got.node_id,
            log_level=got.log_level,
            messages=got.messages,
        )
        callback = self._log_streamers.get(item.job_id)
        if callback is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not forward log because a logstreamer associated with job_id={item.job_id} was not registered",
            )
        await callback(item)
        return True

    async def register(
        self, job_id: JobID, callback: Callable[[JobLog], Awaitable[None]]
    ):
        if job_id in self._log_streamers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A stream was already connected to {job_id=}. Only a single stream can be connected at the time",
            )
        self._log_streamers[job_id] = callback
        await self._rabbit_client.add_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )

    async def deregister(self, job_id: JobID):
        if not job_id in self._log_streamers:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No stream was connected to {job_id=}.",
            )
        await self._rabbit_client.remove_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )
        del self._log_streamers[job_id]


class LogStreamer:
    _queue: Queue[JobLog]
    _queue_name: str
    _job_id: JobID
    _user_id: PositiveInt
    _director2_api: DirectorV2Api

    def __init__(
        self,
        user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
        director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    ):
        self._user_id = user_id
        self._director2_api = director2_api
        self._queue: Queue[JobLog] = Queue()

    async def register(self, job_id: JobID, log_distributor: LogDistributor):
        self._job_id = job_id
        await log_distributor.register(job_id, self._queue.put)

    async def deregister(self, log_distributor: LogDistributor):
        await log_distributor.deregister(self._job_id)

    async def _project_done(self) -> bool:
        task = await self._director2_api.get_computation(self._job_id, self._user_id)
        return not task.stopped is None

    async def log_generator(self) -> AsyncIterable[str]:
        while True:
            while self._queue.empty():
                if await self._project_done():
                    return
                await asyncio.sleep(10)
            log: JobLog = await self._queue.get()
            yield log.json() + _NEW_LINE
