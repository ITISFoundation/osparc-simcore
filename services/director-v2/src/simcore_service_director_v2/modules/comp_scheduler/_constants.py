import datetime
from typing import Final

MODULE_NAME_SCHEDULER: Final[str] = "computational-distributed-scheduler"
MODULE_NAME_WORKER: Final[str] = "computational-distributed-worker"
MODULE_NAME_RELEASER: Final[str] = "computational-distributed-releaser"
SCHEDULER_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)
MAX_CONCURRENT_PIPELINE_SCHEDULING: Final[int] = 10
TASK_RESULT_RELEASE_CONCURRENCY: Final[int] = 5
# NOTE: on-demand clusters may take up to COMPUTATIONAL_BACKEND_MAX_WAITING_FOR_CLUSTER_TIMEOUT
# (10 minutes by default) to start, so the retry window must comfortably outlast that instead
# of using rabbitmq's short (~15s) defaults, otherwise the release would be dropped for good
# while the cluster is still starting up.
TASK_RESULT_RELEASE_RETRY_DELAY: Final[datetime.timedelta] = datetime.timedelta(seconds=30)
TASK_RESULT_RELEASE_MAX_ATTEMPTS: Final[int] = 30
