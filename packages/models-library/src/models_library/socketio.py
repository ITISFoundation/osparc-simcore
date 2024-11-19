from typing import Any

from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)


class SocketMessageDict(TypedDict):
    event_type: str
    data: dict[str, Any]
