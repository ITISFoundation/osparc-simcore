from typing import Any

from typing_extensions import TypedDict


class SocketMessageDict(TypedDict):
    event_type: str
    data: dict[str, Any]
