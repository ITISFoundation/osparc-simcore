import datetime
from typing import Final

from pydantic import NonNegativeInt

DEFAULT_LOCK_TTL: Final[datetime.timedelta] = datetime.timedelta(seconds=10)
DEFAULT_SOCKET_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=30)

DEFAULT_SEMAPHORE_TTL: Final[datetime.timedelta] = datetime.timedelta(minutes=10)
SEMAPHORE_KEY_PREFIX: Final[str] = "semaphores:"
SEMAPHORE_HOLDER_KEY_PREFIX: Final[str] = "semaphore_holders:"

DEFAULT_DECODE_RESPONSES: Final[bool] = True
DEFAULT_HEALTH_CHECK_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)
SHUTDOWN_TIMEOUT_S: Final[NonNegativeInt] = 5
