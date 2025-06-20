import logging
from collections.abc import Awaitable
from typing import Any

import click
from dask.typing import Key
from distributed import WorkerPlugin
from distributed.worker import Worker
from distributed.worker_state_machine import TaskStateState

from ..models import TASK_LIFE_CYCLE_EVENT, TaskLifeCycleState

_logger = logging.getLogger(__name__)


class TaskLifecycleWorkerPlugin(WorkerPlugin):
    def __init__(self) -> None:
        self._worker: Worker | None = None
        _logger.info("TaskLifecycleWorkerPlugin initialized")

    def setup(self, worker: Worker) -> Awaitable[None]:
        async def _() -> None:
            self._worker = worker
            _logger.info("TaskLifecycleWorkerPlugin setup completed")

        return _()

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        **kwargs: Any,
    ):
        _logger.info("Task '%s' transition from %s to %s", key, start, finish)
        assert self._worker  # nosec
        self._worker.log_event(
            TASK_LIFE_CYCLE_EVENT.format(key=key),
            TaskLifeCycleState.from_worker_task_state(
                key, kwargs.get("worker"), finish
            ).model_dump(mode="json"),
        )


@click.command()
async def dask_setup(worker: Worker) -> None:
    plugin = TaskLifecycleWorkerPlugin()
    await worker.plugin_add(plugin)
