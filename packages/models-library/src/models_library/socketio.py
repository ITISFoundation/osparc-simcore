from typing import Any, TypedDict


class SocketMessageDict(TypedDict):
    event_type: str
    data: dict[str, Any]
