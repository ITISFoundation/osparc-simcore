import logging
from dataclasses import asdict, dataclass
from typing import Any, Final

from dask.typing import Key
from distributed import Scheduler, SchedulerPlugin
from distributed.scheduler import TaskStateState
from models_library.projects_state import RunningState
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


_TASK_LIFE_CYCLE_EVENT: Final[str] = "task-lifecycle-{key}"
_SCHEDULER_TASK_STATE_TO_RUNNING_STATE: Final[dict[TaskStateState, RunningState]] = {}


@dataclass
class TaskLifeCycleState:
    key: Key
    worker: str | None
    state: RunningState

    @classmethod
    def from_scheduler_task_state(
        cls, key: Key, worker: str | None, task_state: TaskStateState
    ) -> "TaskLifeCycleState":
        return cls(
            key=key,
            worker=worker,
            state=_SCHEDULER_TASK_STATE_TO_RUNNING_STATE[task_state],
        )


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
        *args: Any,  # noqa: ARG002
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
                _TASK_LIFE_CYCLE_EVENT.format(key=key),
                asdict(
                    TaskLifeCycleState.from_scheduler_task_state(
                        key, kwargs.get("worker"), finish
                    )
                ),
            )
