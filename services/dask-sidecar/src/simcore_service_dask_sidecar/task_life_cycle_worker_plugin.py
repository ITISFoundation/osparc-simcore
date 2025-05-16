import logging
from collections.abc import Awaitable
from typing import Any

from dask.typing import Key
from dask_task_models_library.models import TASK_LIFE_CYCLE_EVENT, TaskLifeCycleState
from distributed import WorkerPlugin
from distributed.worker import Worker
from distributed.worker_state_machine import TaskStateState
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


class TaskLifecycleWorkerPlugin(WorkerPlugin):
    def __init__(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            "TaskLifecycleWorkerPlugin init",
        ):
            self._worker = None

    def setup(self, worker: Worker) -> Awaitable[None]:
        async def _() -> None:
            with log_context(
                _logger,
                logging.INFO,
                "TaskLifecycleWorkerPlugin start",
            ):
                self._worker = worker  # type: ignore[assignment]

        return _()

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        **kwargs: Any,
    ):
        with log_context(
            _logger,
            logging.INFO,
            f"Task {key!r} transition from {start} to {finish}",
        ):
            assert self._worker  # nosec
            self._worker.log_event(
                TASK_LIFE_CYCLE_EVENT.format(key=key),
                TaskLifeCycleState.from_worker_task_state(
                    key, kwargs.get("worker"), finish
                ).model_dump(mode="json"),
            )
