import asyncio
from asyncio.queues import Queue
from typing import Annotated, AsyncIterable, Awaitable, Callable, Final, cast
from uuid import UUID

from fastapi import Depends, FastAPI
from models_library.projects import ProjectID
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


def get_job_log_distributor(
    app: Annotated[FastAPI, Depends(get_app)]
) -> "JobLogDistributor":
    assert app.state.log_distributor  # nosec
    return cast(JobLogDistributor, app.state.log_distibutor)


class JobLogDistributor:
    _log_queue_callbacks: dict[JobID, Callable[[JobLog], Awaitable[bool]]]
    _rabbit_client: RabbitMQClient
    _queue_name: str

    def __init__(
        self,
        rabbit_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client)],
    ):
        self._log_queue_callbacks = {}
        self._rabbit_client = rabbit_client

    async def setup(self):
        self._queue_name = await self._rabbit_client.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._distribute_log,
            exclusive_queue=True,
            topics=[],
        )

    async def teardown(self):
        await self._rabbit_client.unsubscribe(self._queue_name)

    async def register_streamer(
        self, job_id: JobID, callback: Callable[[JobLog], Awaitable[bool]]
    ):
        self._log_queue_callbacks[job_id] = callback
        await self._rabbit_client.add_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )

    async def deregister_streamer(self, job_id: JobID):
        assert (
            job_id in self._log_queue_callbacks
        ), f"{job_id=} was not in list of callbacks"
        await self._rabbit_client.remove_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )
        del self._log_queue_callbacks[job_id]

    async def _distribute_log(self, data: bytes) -> bool:
        got = LoggerRabbitMessage.parse_raw(data)
        item = JobLog(
            job_id=got.project_id,
            node_id=got.node_id,
            log_level=got.log_level,
            messages=got.messages,
        )
        assert (
            callback := self._log_queue_callbacks.get(item.job_id)
        ) is not None, f"No logstreamer for {item.job_id=} was not registered"
        return await callback(item)


class LogStreamer:
    _queue: Queue[JobLog]
    _queue_name: str
    _job_id: ProjectID
    _user_id: PositiveInt
    _director2_api: DirectorV2Api
    _distributor = JobLogDistributor

    def __init__(
        self,
        user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
        distributor: Annotated[JobLogDistributor, Depends(get_job_log_distributor)],
        director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    ):
        self._distributor = distributor
        self._user_id = user_id
        self._director2_api = director2_api
        self._queue: Queue[JobLog] = Queue(50)

    async def listen(
        self,
        project_id: UUID,
    ):
        self._job_id = project_id
        await self._distributor.register_streamer(self._job_id, self._add_logs_to_queue)

    async def stop_listening(self):
        await self._distributor.deregister_streamer(job_id=self._job_id)

    async def _add_logs_to_queue(self, job_log: JobLog) -> bool:
        await self._queue.put(job_log)
        return True

    async def _project_done(self) -> bool:
        task = await self._director2_api.get_computation(self._job_id, self._user_id)
        return not task.stopped is None

    async def log_generator(self) -> AsyncIterable[str]:
        while True:
            while self._queue.empty():
                if await self._project_done():
                    return
                await asyncio.sleep(5)
            log: JobLog = await self._queue.get()
            yield log.json() + _NEW_LINE
