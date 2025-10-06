import functools
import logging
from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI
from faststream.exceptions import FastStreamException, RejectMessage
from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitQueue,
    RabbitRouter,
)
from faststream.rabbit.schemas.queue import ClassicQueueArgs
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ...core.settings import ApplicationSettings
from ._core import Core
from ._event_after import AfterEventManager
from ._lifecycle_protocol import SupportsLifecycle
from ._models import EventType, OperationContext, OperationName, ScheduleId

_logger = logging.getLogger(__name__)


_EXCHANGE_NAME: Final[str] = __name__


def _get_global_queue(
    queue_name: str, arguments: ClassicQueueArgs | None = None
) -> RabbitQueue:
    return RabbitQueue(
        f"{_EXCHANGE_NAME}_{queue_name}", durable=True, arguments=arguments
    )


def _stop_retry_for_unintended_errors(func):
    """
    Stops FastStream's retry chain when an unexpected error is raised (bug or otherwise).
    This is especially important when the subscribers have ``retry=True``.

    Only propagate FastStream error that handle message acknowledgement.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, FastStreamException):
                # if there are issues with Redis or FastStream (core dependencies)
                # message is always retried
                raise

            msg = (
                "Unexpected error. Aborting message retry. "
                f"Please check code at: '{func.__module__}.{func.__name__}'"
            )
            _logger.exception(msg)
            raise RejectMessage from e

    return wrapper


@dataclass
class _OperationToStartEvent:
    schedule_id: ScheduleId
    operation_name: OperationName
    initial_context: OperationContext


class EventScheduler(  # pylint: disable=too-many-instance-attributes
    SingletonInAppStateMixin, SupportsLifecycle
):
    """Handles scheduling of single events for a given schedule_id"""

    app_state_name: str = "generic_scheduler_event_scheduler"

    def __init__(self, app: FastAPI) -> None:
        self.app = app

        settings: ApplicationSettings = app.state.settings

        self._broker: RabbitBroker = RabbitBroker(
            settings.DYNAMIC_SCHEDULER_RABBITMQ.dsn, log_level=logging.DEBUG
        )
        self._router: RabbitRouter = RabbitRouter()
        self._exchange = RabbitExchange(
            _EXCHANGE_NAME, durable=True, type=ExchangeType.DIRECT
        )
        self._queue_schedule_event = _get_global_queue(queue_name="schedule_queue")
        self._queue_create_completed_event = _get_global_queue(
            queue_name="create_completed_queue"
        )
        self._queue_undo_completed_event = _get_global_queue(
            queue_name="undo_completed_queue"
        )

    @_stop_retry_for_unintended_errors
    async def _on_safe_on_schedule_event(  # pylint:disable=method-hidden
        self, schedule_id: ScheduleId
    ) -> None:
        await Core.get_from_app_state(self.app).safe_on_schedule_event(schedule_id)

    @_stop_retry_for_unintended_errors
    async def _on_created_completed_event(  # pylint:disable=method-hidden
        self, event: _OperationToStartEvent
    ) -> None:
        await AfterEventManager.get_from_app_state(self.app).safe_on_event_type(
            EventType.ON_CREATED_COMPLETED,
            event.schedule_id,
            event.operation_name,
            event.initial_context,
        )

    @_stop_retry_for_unintended_errors
    async def _on_undo_completed_event(  # pylint:disable=method-hidden
        self, event: _OperationToStartEvent
    ) -> None:
        await AfterEventManager.get_from_app_state(self.app).safe_on_event_type(
            EventType.ON_UNDO_COMPLETED,
            event.schedule_id,
            event.operation_name,
            event.initial_context,
        )

    async def enqueue_schedule_event(self, schedule_id: ScheduleId) -> None:
        await self._broker.publish(
            schedule_id,
            queue=self._queue_schedule_event,
            exchange=self._exchange,
        )

    async def enqueue_create_completed_event(
        self,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        initial_context: OperationContext,
    ) -> None:
        await self._broker.publish(
            _OperationToStartEvent(
                schedule_id=schedule_id,
                operation_name=operation_name,
                initial_context=initial_context,
            ),
            queue=self._queue_create_completed_event,
            exchange=self._exchange,
        )

    async def enqueue_undo_completed_event(
        self,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        initial_context: OperationContext,
    ) -> None:
        await self._broker.publish(
            _OperationToStartEvent(
                schedule_id=schedule_id,
                operation_name=operation_name,
                initial_context=initial_context,
            ),
            queue=self._queue_undo_completed_event,
            exchange=self._exchange,
        )

    def _register_subscribers(self) -> None:
        # pylint:disable=unexpected-keyword-arg
        # pylint:disable=no-value-for-parameter

        self._on_safe_on_schedule_event = self._router.subscriber(
            queue=self._queue_schedule_event,
            exchange=self._exchange,
            retry=True,
        )(self._on_safe_on_schedule_event)

        self._on_created_completed_event = self._router.subscriber(
            queue=self._queue_create_completed_event,
            exchange=self._exchange,
            retry=True,
        )(self._on_created_completed_event)

        self._on_undo_completed_event = self._router.subscriber(
            queue=self._queue_undo_completed_event,
            exchange=self._exchange,
            retry=True,
        )(self._on_undo_completed_event)

    async def setup(self) -> None:
        self._register_subscribers()
        self._broker.include_router(self._router)

        await self._broker.start()

    async def shutdown(self) -> None:
        await self._broker.close()
