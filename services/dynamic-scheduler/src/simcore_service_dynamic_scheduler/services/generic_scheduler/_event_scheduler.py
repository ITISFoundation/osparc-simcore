import functools
import logging
from collections.abc import AsyncIterator
from typing import Final

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from faststream.exceptions import FastStreamException, RejectMessage
from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitQueue,
    RabbitRouter,
)

from ...core.settings import ApplicationSettings
from ._core import get_core
from ._models import ScheduleId

_logger = logging.getLogger(__name__)


_EXCHANGE_NAME: Final[str] = __name__
_QUEUE_NAME: Final[str] = "event_scheduler"


def _get_global_queue(queue_name: str) -> RabbitQueue:
    return RabbitQueue(f"{_EXCHANGE_NAME}_{queue_name}", durable=True)


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


class EventScheduler:
    """Handles scheduling of single events for a given schedule_id"""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

        settings: ApplicationSettings = app.state.settings

        self.broker: RabbitBroker = RabbitBroker(
            settings.DYNAMIC_SCHEDULER_RABBITMQ.dsn, log_level=logging.DEBUG
        )
        self.router: RabbitRouter = RabbitRouter()
        self.exchange = RabbitExchange(
            _EXCHANGE_NAME, durable=True, type=ExchangeType.DIRECT
        )

    @_stop_retry_for_unintended_errors
    async def _on_secure_schedule_event(  # pylint:disable=method-hidden
        self, schedule_id: ScheduleId
    ) -> None:
        # advance operation
        # NOTE: should no longer forward operation if nothing needs doing
        # an unexpected error might be raised
        await get_core(self.app).safe_on_schedule_event(schedule_id)

    async def enqueue_event(self, schedule_id: ScheduleId) -> None:
        await self.broker.publish(
            schedule_id, queue=_get_global_queue(_QUEUE_NAME), exchange=self.exchange
        )

    def _register_subscribers(self) -> None:
        # pylint:disable=unexpected-keyword-arg
        # pylint:disable=no-value-for-parameter
        self._on_secure_schedule_event = self.router.subscriber(
            queue=_get_global_queue(_QUEUE_NAME),
            exchange=self.exchange,
            retry=True,
        )(self._on_secure_schedule_event)

    async def setup(self) -> None:
        self._register_subscribers()
        self.broker.include_router(self.router)

        await self.broker.start()

    async def shutdown(self) -> None:
        await self.broker.close()


async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.generic_scheduler_event_scheduler = event_scheduler = EventScheduler(app)
    await event_scheduler.setup()
    yield {}
    await event_scheduler.shutdown()
