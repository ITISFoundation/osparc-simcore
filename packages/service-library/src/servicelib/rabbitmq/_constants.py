from typing import Final

from pydantic import PositiveInt

BIND_TO_ALL_TOPICS: Final[str] = "#"
RPC_REQUEST_DEFAULT_TIMEOUT_S: Final[PositiveInt] = PositiveInt(5)
RPC_REMOTE_METHOD_TIMEOUT_S: Final[int] = 30
