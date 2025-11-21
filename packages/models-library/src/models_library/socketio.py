from typing import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    Any,
    TypedDict,
)


class SocketMessageDict(TypedDict):
    event_type: str
    data: dict[str, Any]
