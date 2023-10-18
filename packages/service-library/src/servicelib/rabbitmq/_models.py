import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from models_library.rabbitmq_basic_types import (
    REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS,
    RPCNamespace,
)
from pydantic import ConstrainedStr, parse_obj_as

MessageHandler = Callable[[Any], Awaitable[bool]]


class RabbitMessage(Protocol):
    def body(self) -> bytes:
        ...

    def routing_key(self) -> str | None:
        ...


class RPCMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 252
    regex: re.Pattern[str] | None = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)


class RPCNamespacedMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 255
    regex: re.Pattern[str] | None = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)

    @classmethod
    def from_namespace_and_method(
        cls, namespace: RPCNamespace, method_name: RPCMethodName
    ) -> "RPCNamespacedMethodName":
        namespaced_method_name = f"{namespace}.{method_name}"
        return parse_obj_as(cls, namespaced_method_name)


__all__: tuple[str, ...] = ("RPCNamespace",)
