import logging
from typing import Any

from dask.typing import Key
from distributed import Scheduler, SchedulerPlugin
from distributed.scheduler import TaskStateState
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


class TaskLifecycleSchedulerPlugin(SchedulerPlugin):
    def __init__(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            "TaskLifecycleSchedulerPlugin init",
        ):
            self.scheduler = None

    async def start(self, scheduler: Scheduler) -> None:
        with log_context(
            _logger,
            logging.INFO,
            "TaskLifecycleSchedulerPlugin start",
        ):
            self.scheduler = scheduler

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        *args: Any,
        stimulus_id: str,
        **kwargs: Any,
    ):
        # Start state: one of released, waiting, processing, memory, error
        with log_context(
            _logger,
            logging.INFO,
            f"Task {key} transition from {start} to {finish} due to {stimulus_id=}",
        ):
            assert self.scheduler  # nosec
            self.scheduler.log_event(
                f"task-lifecycle-{key}",
                {
                    "key": key,
                    "worker": kwargs.get("worker"),
                    "start": start,
                    "finish": finish,
                    "stimulus_id": stimulus_id,
                },
            )
