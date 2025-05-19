import logging
from typing import Any

import click
from dask.typing import Key
from distributed import Scheduler, SchedulerPlugin
from distributed.scheduler import TaskStateState
from servicelib.logging_utils import log_context

from ..models import TASK_LIFE_CYCLE_EVENT, TaskLifeCycleState

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
            self.scheduler = scheduler  # type: ignore[assignment]

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        *args: Any,  # noqa: ARG002
        stimulus_id: str,
        **kwargs: Any,
    ):
        with log_context(
            _logger,
            logging.INFO,
            f"Task {key!r} transition from {start} to {finish} due to {stimulus_id=}",
        ):
            assert self.scheduler  # nosec

            self.scheduler.log_event(
                TASK_LIFE_CYCLE_EVENT.format(key=key),
                TaskLifeCycleState.from_scheduler_task_state(
                    key, kwargs.get("worker"), finish
                ).model_dump(mode="json"),
            )


@click.command()
def dask_setup(scheduler):
    plugin = TaskLifecycleSchedulerPlugin()
    scheduler.add_plugin(plugin)
