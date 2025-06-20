# pylint: disable=unused-argument
import logging
from typing import Any

import click
from dask.typing import Key
from distributed import Scheduler, SchedulerPlugin
from distributed.scheduler import TaskStateState

from ..models import TASK_LIFE_CYCLE_EVENT, TaskLifeCycleState

_logger = logging.getLogger(__name__)


class TaskLifecycleSchedulerPlugin(SchedulerPlugin):
    def __init__(self) -> None:
        self.scheduler: Scheduler | None = None
        _logger.info("initialized TaskLifecycleSchedulerPlugin")

    async def start(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler
        _logger.info("started TaskLifecycleSchedulerPlugin")

    def transition(
        self,
        key: Key,
        start: TaskStateState,
        finish: TaskStateState,
        *args: Any,  # noqa: ARG002
        stimulus_id: str,
        **kwargs: Any,
    ):
        _logger.debug(
            "Task %s transition from %s to %s due to %s",
            key,
            start,
            finish,
            stimulus_id,
        )

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
