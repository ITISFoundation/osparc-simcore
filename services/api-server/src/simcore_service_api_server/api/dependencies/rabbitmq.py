import asyncio
from asyncio.queues import Queue
from typing import Annotated, AsyncIterable, Final
from uuid import UUID

from fastapi import Depends
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import LoggerRabbitMessage
from pydantic import PositiveInt
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.api.dependencies.authentication import (
    get_current_user_id,
)
from simcore_service_api_server.api.dependencies.services import get_api_client
from simcore_service_api_server.models.schemas.jobs import JobLog
from simcore_service_api_server.services.director_v2 import DirectorV2Api
from starlette.background import BackgroundTask

_NEW_LINE: Final[str] = "\n"


class LogListener:
    _queue: Queue[JobLog]
    _queu_name: str
    _rabbit_consumer: RabbitMQClient
    _project_id: ProjectID
    _user_id: PositiveInt
    _director2_api: DirectorV2Api

    @classmethod
    async def create(
        cls,
        rabbit_consumer: RabbitMQClient,
        project_id: UUID,
        user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
        director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    ) -> "LogListener":
        self = cls()
        self._rabbit_consumer = rabbit_consumer
        self._project_id = project_id
        self._user_id = user_id
        self._director2_api = director2_api

        self._queue = Queue()
        self._queu_name = await self._rabbit_consumer.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._add_logs_to_queu,
            exclusive_queue=True,
            topics=[f"{self._project_id}.*"],
        )
        return self

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
