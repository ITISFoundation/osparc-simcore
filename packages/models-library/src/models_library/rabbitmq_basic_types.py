import re
from typing import Final

from pydantic import ConstrainedStr, parse_obj_as

REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS: Final[str] = r"^[\w\-\.]*$"


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
