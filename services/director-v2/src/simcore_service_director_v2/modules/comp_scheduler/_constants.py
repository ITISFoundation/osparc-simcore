import datetime
from typing import Final

MODULE_NAME_SCHEDULER: Final[str] = "computational-distributed-scheduler"
MODULE_NAME_WORKER: Final[str] = "computational-distributed-worker"
SCHEDULER_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)
MAX_CONCURRENT_PIPELINE_SCHEDULING: Final[int] = 10
