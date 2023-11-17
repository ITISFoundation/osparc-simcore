from asyncio.queues import Queue
from typing import AsyncIterable, Final
from uuid import UUID

from models_library.rabbitmq_messages import LoggerRabbitMessage
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.models.schemas.jobs import JobLog
from starlette.background import BackgroundTask

_NEW_LINE: Final[str] = "\n"


class LogListener:
    _queue: Queue[JobLog]
    _queu_name: str
    _rabbit_consumer: RabbitMQClient

    @classmethod
    async def create(
        cls,
        rabbit_consumer: RabbitMQClient,
        project_id: UUID,
    ) -> "LogListener":
        self = cls()
        self._queue = Queue()
        self._rabbit_consumer = rabbit_consumer
        self._queu_name = await self._rabbit_consumer.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._add_logs_to_queu,
            exclusive_queue=True,
            topics=[f"{project_id}.*"],
        )
        return self

    def unsubscribe_task(self) -> BackgroundTask:
        return BackgroundTask(self._rabbit_consumer.unsubscribe, self._queu_name)

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

    async def log_generator(self) -> AsyncIterable[str]:
        while True:
            log: JobLog = await self._queue.get()
            yield log.json() + _NEW_LINE
