import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI
from faststream.exceptions import FastStreamException, RejectMessage
from faststream.rabbit import RabbitExchange, RabbitQueue, RabbitRouter
from faststream.rabbit.schemas.queue import QueueType, QuorumQueueArgs

from ._models import OperationContext, OperationName, ScheduleId

_logger = logging.getLogger(__name__)


EXCHANGE_NAME: Final[str] = "dynamic-scheduler-events"


def _get_global_queue(queue_name: str, arguments: QuorumQueueArgs | None = None) -> RabbitQueue:
    # See https://github.com/ITISFoundation/osparc-simcore/pull/8573
    # to understand why QUORUM queues are used here
    return RabbitQueue(
        f"{EXCHANGE_NAME}_{queue_name}",
        queue_type=QueueType.QUORUM,
        durable=True,  # RabbitQueue typing requires durable=True when queue_type is QUORUM
        arguments=arguments,
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

            msg = f"Unexpected error. Aborting message retry. Please check code at: '{func.__module__}.{func.__name__}'"
            _logger.exception(msg)
            raise RejectMessage from e

    return wrapper


@dataclass
class OperationToStartEvent:
    schedule_id: ScheduleId
    operation_name: OperationName
    initial_context: OperationContext


@dataclass
class BaseEventQueue(ABC):
    app: FastAPI
    router: RabbitRouter
    exchange: RabbitExchange

    _queue: RabbitQueue | None = None

    @classmethod
    def get_queue_name(cls) -> str:
        return cls.__name__

    @property
    def queue(self) -> RabbitQueue:
        assert self._queue is not None  # nosec
        return self._queue

    def __post_init__(self):
        self._queue = _get_global_queue(queue_name=self.get_queue_name())

        # apply decorators
        handler = _stop_retry_for_unintended_errors(self.handler)
        handler = self.router.subscriber(queue=self._queue, exchange=self.exchange, retry=True)(handler)

    @abstractmethod
    async def handler(self, **kwargs) -> None:
        """implement actions to take after event is received"""
