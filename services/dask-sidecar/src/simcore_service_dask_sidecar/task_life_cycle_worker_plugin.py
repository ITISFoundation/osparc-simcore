import logging
from collections.abc import Awaitable
from typing import Any

from dask.typing import Key
from distributed import Worker, WorkerPlugin
from distributed.scheduler import TaskStateState
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


class TaskLifecycleWorkerPlugin(WorkerPlugin):
    def __init__(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            "TaskLifecycleWorkerPlugin init",
        ):
            self.worker = None

    def setup(self, worker: Worker) -> Awaitable[None]:
        async def _() -> None:
            with log_context(
                _logger,
                logging.INFO,
                "TaskLifecycleWorkerPlugin start",
            ):
                self.worker = worker

        return _()

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        **kwargs: Any,
    ):
        # Start state: one of released, waiting, processing, memory, error
        with log_context(
            _logger,
            logging.INFO,
            f"Task {key} transition from {start} to {finish}",
        ):
            assert self.worker  # nosec
            self.worker.log_event(
                f"task-lifecycle-{key}",
                {
                    "key": key,
                    "worker": kwargs.get("worker"),
                    "start": start,
                    "finish": finish,
                },
            )
