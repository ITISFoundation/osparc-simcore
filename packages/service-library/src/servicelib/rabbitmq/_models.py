import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import ConstrainedStr, parse_obj_as

from ._constants import REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS

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


class RPCNamespace(ConstrainedStr):
    min_length: int = 1
    max_length: int = 252
    regex: re.Pattern[str] | None = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)

    @classmethod
    def from_entries(cls, entries: dict[str, str]) -> "RPCNamespace":
        """
        Given a list of entries creates a namespace to be used in declaring the rabbitmq queue.
        Keeping this to a predefined length
        """
        composed_string = "-".join(f"{k}_{v}" for k, v in sorted(entries.items()))
        return parse_obj_as(cls, composed_string)


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
