import re
from typing import Final

from pydantic import StringConstraints

REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS: Final[str] = r"^[\w\-\.]*$"


class RPCNamespace(str, StringConstraints):
    min_length: int = 1
    max_length: int = 252
    pattern: str | re.Pattern[str] | None = REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS

    @classmethod
    def from_entries(cls, entries: dict[str, str]) -> "RPCNamespace":
        """
        Given a list of entries creates a namespace to be used in declaring the rabbitmq queue.
        Keeping this to a predefined length
        """
        composed_string = "-".join(f"{k}_{v}" for k, v in sorted(entries.items()))
        return cls(composed_string)


class RPCMethodName(str, StringConstraints):
    min_length: int = 1
    max_length: int = 252
    pattern: str | re.Pattern[str] | None = REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS
