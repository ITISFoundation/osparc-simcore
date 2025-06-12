from datetime import timedelta
from typing import Final

DEFAULT_POLL_INTERVAL_S: Final[float] = 1

DEFAULT_STALE_TASK_CHECK_INTERVAL: Final[timedelta] = timedelta(minutes=1)
DEFAULT_STALE_TASK_DETECT_TIMEOUT: Final[timedelta] = timedelta(minutes=5)
