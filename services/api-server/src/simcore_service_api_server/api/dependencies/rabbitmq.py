import asyncio
from asyncio.queues import Queue
from typing import Annotated, AsyncIterable, Final, cast
from uuid import UUID

from fastapi import Depends, FastAPI
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from pydantic import PositiveInt
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.api.dependencies.authentication import (
    get_current_user_id,
)
from simcore_service_api_server.api.dependencies.services import get_api_client
from simcore_service_api_server.models.schemas.jobs import JobLog
from simcore_service_api_server.services.director_v2 import DirectorV2Api
from starlette.background import BackgroundTask

_NEW_LINE: Final[str] = "\n"


def get_rabbitmq_client(app: Annotated[FastAPI, Depends(get_app)]) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


class LogListener:
    _queue: Queue[JobLog]
    _queu_name: str
    _rabbit_consumer: RabbitMQClient
    _project_id: ProjectID
    _user_id: PositiveInt
    _director2_api: DirectorV2Api

    def __init__(
        self,
        user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
        rabbit_consumer: Annotated[RabbitMQClient, Depends(get_rabbitmq_client)],
        director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    ):

        self._rabbit_consumer = rabbit_consumer
        self._user_id = user_id
        self._director2_api = director2_api
        self._queue: Queue[JobLog] = Queue()

    async def listen(
        self,
        project_id: UUID,
    ):
        self._project_id = project_id

        self._queu_name = await self._rabbit_consumer.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._add_logs_to_queu,
            exclusive_queue=True,
            topics=[f"{self._project_id}.*"],
        )

    async def _add_logs_to_queu(self, data: bytes):
        got = LoggerRabbitMessage.parse_raw(data)
        item = JobLog(
            job_id=got.project_id,
            node_id=got.node_id,
            log_level=got.log_level,
            messages=got.messages,
        )
        await self._queue.put(item)
        return True

    async def _project_done(self) -> bool:
        task = await self._director2_api.get_computation(
            self._project_id, self._user_id
        )
        return not task.stopped is None

    async def log_generator(self) -> AsyncIterable[str]:
        while True:
            while self._queue.empty():
                if await self._project_done():
                    raise StopAsyncIteration
                await asyncio.sleep(5)
            log: JobLog = await self._queue.get()
            yield log.json() + _NEW_LINE

    def unsubscribe_task(self) -> BackgroundTask:
        return BackgroundTask(self._rabbit_consumer.unsubscribe, self._queu_name)
