from dataclasses import asdict, dataclass
from typing import Any, Final, TypeAlias

from dask.typing import Key
from distributed.scheduler import TaskStateState as SchedulerTaskState
from distributed.worker_state_machine import TaskStateState as WorkerTaskState
from models_library.projects_state import RunningState

DaskJobID: TypeAlias = str
DaskResources: TypeAlias = dict[str, int | float]

TASK_LIFE_CYCLE_EVENT: Final[str] = "task-lifecycle-{key}"
_SCHEDULER_TASK_STATE_TO_RUNNING_STATE: Final[
    dict[SchedulerTaskState, RunningState]
] = {
    "waiting": RunningState.PENDING,
    "no-worker": RunningState.WAITING_FOR_RESOURCES,
    "queued": RunningState.WAITING_FOR_RESOURCES,
    "processing": RunningState.PENDING,
    "memory": RunningState.SUCCESS,
    "erred": RunningState.FAILED,
    "forgotten": RunningState.UNKNOWN,
}

_WORKER_TASK_STATE_TO_RUNNING_STATE: Final[dict[WorkerTaskState, RunningState]] = {
    "cancelled": RunningState.UNKNOWN,
    "constrained": RunningState.UNKNOWN,
    "error": RunningState.UNKNOWN,
    "executing": RunningState.UNKNOWN,
    "fetch": RunningState.UNKNOWN,
    "flight": RunningState.UNKNOWN,
    "forgotten": RunningState.UNKNOWN,
    "long-running": RunningState.UNKNOWN,
    "memory": RunningState.UNKNOWN,
    "missing": RunningState.UNKNOWN,
    "ready": RunningState.UNKNOWN,
    "released": RunningState.UNKNOWN,
    "rescheduled": RunningState.UNKNOWN,
    "resumed": RunningState.UNKNOWN,
    "waiting": RunningState.UNKNOWN,
}


@dataclass
class TaskLifeCycleState:
    key: Key
    worker: str | None
    state: RunningState

    @classmethod
    def from_scheduler_task_state(
        cls, key: Key, worker: str | None, task_state: SchedulerTaskState
    ) -> "TaskLifeCycleState":
        return cls(
            key=key,
            worker=worker,
            state=_SCHEDULER_TASK_STATE_TO_RUNNING_STATE[task_state],
        )

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)
