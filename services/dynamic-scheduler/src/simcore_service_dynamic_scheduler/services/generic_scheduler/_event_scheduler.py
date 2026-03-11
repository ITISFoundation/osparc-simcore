import logging

from fastapi import FastAPI
from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitRouter,
)
from faststream.rabbit.types import AioPikaSendableMessage
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ...core.settings import ApplicationSettings
from ._event_base_queue import EXCHANGE_NAME, BaseEventQueue
from ._event_queues import ExecuteCompletedQueue, RevertCompletedQueue, ScheduleQueue
from ._lifecycle_protocol import SupportsLifecycle


class EventScheduler(SingletonInAppStateMixin, SupportsLifecycle):
    """Handles scheduling of single events for a given schedule_id"""

    app_state_name: str = "generic_scheduler_event_scheduler"

    def __init__(self, app: FastAPI) -> None:
        self.app = app

        settings: ApplicationSettings = app.state.settings

        self._broker: RabbitBroker = RabbitBroker(settings.DYNAMIC_SCHEDULER_RABBITMQ.dsn, log_level=logging.DEBUG)
        self._router: RabbitRouter = RabbitRouter()
        self._exchange = RabbitExchange(EXCHANGE_NAME, durable=True, type=ExchangeType.DIRECT)

        self._queues: dict[str, BaseEventQueue] = {
            queue_class.get_queue_name(): queue_class(app, self._router, self._exchange)
            for queue_class in (
                ScheduleQueue,
                ExecuteCompletedQueue,
                RevertCompletedQueue,
            )
        }

    async def enqueue_message_for(self, queue_class: type[BaseEventQueue], message: AioPikaSendableMessage) -> None:
        await self._broker.publish(
            message,
            queue=self._queues[queue_class.get_queue_name()].queue,
            exchange=self._exchange,
        )

    async def setup(self) -> None:
        self._broker.include_router(self._router)
        await self._broker.start()

    async def shutdown(self) -> None:
        await self._broker.close()
