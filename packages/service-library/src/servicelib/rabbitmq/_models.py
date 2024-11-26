from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeAlias

from models_library.basic_types import ConstrainedStr
from models_library.rabbitmq_basic_types import (
    REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS,
    RPCMethodName,
    RPCNamespace,
)
from pydantic import TypeAdapter

MessageHandler = Callable[[Any], Awaitable[bool]]

ExchangeName: TypeAlias = str
QueueName: TypeAlias = str
ConsumerTag: TypeAlias = str
TopicName: TypeAlias = str


class RabbitMessage(Protocol):
    def body(self) -> bytes: ...

    def routing_key(self) -> str | None: ...


class RPCNamespacedMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 255
    pattern: str = REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS

    @classmethod
    def from_namespace_and_method(
        cls, namespace: RPCNamespace, method_name: RPCMethodName
    ) -> "RPCNamespacedMethodName":
        namespaced_method_name = f"{namespace}.{method_name}"
        return TypeAdapter(cls).validate_python(namespaced_method_name)
