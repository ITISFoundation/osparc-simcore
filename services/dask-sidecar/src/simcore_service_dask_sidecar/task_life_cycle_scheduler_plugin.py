from typing import Any

from dask.typing import Key
from distributed import SchedulerPlugin
from distributed.scheduler import TaskStateState


class SchedulerLifecyclePlugin(SchedulerPlugin):
    def __init__(self) -> None:
        self.scheduler = None

    def add_task(self, key, **kwargs):
        """Task published to cluster"""
        self.scheduler.log_event(
            "task-published",
            {"key": key, "timestamp": time.time(), "client": kwargs.get("client")},
        )

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        **kwargs: Any,
    ):
        """State transitions"""
        if finish in ("waiting", "processing", "memory", "erred"):
            self.scheduler.log_event(
                f"task-{finish}",
                {
                    "key": key,
                    "worker": kwargs.get("worker"),
                    "duration": time.time() - self.scheduler.tasks[key].start_time,
                },
            )
