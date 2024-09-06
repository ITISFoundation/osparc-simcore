from typing import Annotated, Final, Self

from pydantic import RootModel, StringConstraints

REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS: Final[str] = r"^[\w\-\.]*$"


RPCMethodName = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=252, pattern=REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS
    ),
]


class RPCNamespace(RootModel):
    root: RPCMethodName

    @classmethod
    def from_entries(cls, entries: dict[str, str]) -> Self:
        """
        Given a list of entries creates a namespace to be used in declaring the rabbitmq queue.
        Keeping this to a predefined length
        """
        composed_string = "-".join(f"{k}_{v}" for k, v in sorted(entries.items()))
        return cls.model_validate(composed_string)
