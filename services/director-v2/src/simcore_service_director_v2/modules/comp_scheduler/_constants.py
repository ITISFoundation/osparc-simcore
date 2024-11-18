import datetime
from typing import Final

MODULE_NAME: Final[str] = "computational-distributed-scheduler"
SCHEDULER_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)
MAX_CONCURRENT_PIPELINE_SCHEDULING: Final[int] = 10
