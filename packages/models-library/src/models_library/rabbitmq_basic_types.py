from typing import Final

from models_library.basic_types import ConstrainedStr
from pydantic import TypeAdapter

REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS: Final[str] = r"^[\w\-\.]*$"


class RPCNamespace(ConstrainedStr):
    pattern = REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS
    min_length: int = 1
    max_length: int = 252

    @classmethod
    def from_entries(cls, entries: dict[str, str]) -> "RPCNamespace":
        """
        Given a list of entries creates a namespace to be used in declaring the rabbitmq queue.
        Keeping this to a predefined length
        """
        composed_string = "-".join(f"{k}_{v}" for k, v in sorted(entries.items()))
        return TypeAdapter(cls).validate_python(composed_string)


class RPCMethodName(ConstrainedStr):
    pattern = REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS
    min_length: int = 1
    max_length: int = 252
