import datetime
import logging
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, Final, Protocol, TypeAlias

from models_library.basic_types import ConstrainedStr
from models_library.rabbitmq_basic_types import (
    REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS,
    RPCMethodName,
    RPCNamespace,
)
from pydantic import TypeAdapter
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_MINUTE: Final[int] = 60

MessageHandler = Callable[[Any], Awaitable[bool]]

ExchangeName: TypeAlias = str
QueueName: TypeAlias = str
ConsumerTag: TypeAlias = str
TopicName: TypeAlias = str


class RabbitMessage(Protocol):
    def body(self) -> bytes: ...

    def routing_key(self) -> str | None: ...


class _BaseRabbitMQRetryPolicy:
    WAIT: ClassVar[datetime.timedelta]
    STOP_AFTER: ClassVar[datetime.timedelta]

    def __init__(self, logger: logging.Logger | None = None) -> None:
        logger = logger or logging.getLogger(__name__)

        self.kwargs: dict[str, Any] = {
            "wait": wait_fixed(self.WAIT.total_seconds()),
            "stop": stop_after_delay(self.STOP_AFTER.total_seconds()),
            "before_sleep": before_sleep_log(logger, logging.WARNING),
            "reraise": True,
        }


class RabbitMQRetryPolicyUponInitialization(_BaseRabbitMQRetryPolicy):
    WAIT: ClassVar[datetime.timedelta] = datetime.timedelta(seconds=2)
    STOP_AFTER: ClassVar[datetime.timedelta] = datetime.timedelta(minutes=3)


class RabbitMQRetryPolicyUponReconnection(_BaseRabbitMQRetryPolicy):
    """Retry policy to rebuild the RPC surface after a reconnection event.

    The retry budget is deliberately short: the callback runs only once aio-pika has
    already re-established the connection and restored its robust channels, and the rebuild
    executes inside aio-pika's reconnection loop, so a long retry (as upon initialization)
    would delay the detection of the next disconnect (e.g. rolling broker node restarts).
    """

    WAIT: ClassVar[datetime.timedelta] = datetime.timedelta(seconds=1)
    STOP_AFTER: ClassVar[datetime.timedelta] = datetime.timedelta(seconds=15)


class RPCNamespacedMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 255
    pattern: str = REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS

    @classmethod
    def from_namespace_and_method(cls, namespace: RPCNamespace, method_name: RPCMethodName) -> RPCNamespacedMethodName:
        namespaced_method_name = f"{namespace}.{method_name}"
        return TypeAdapter(cls).validate_python(namespaced_method_name)
