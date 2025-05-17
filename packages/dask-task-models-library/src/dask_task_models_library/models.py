from typing import Final, Literal, TypeAlias

from dask.typing import Key
from distributed.scheduler import TaskStateState as SchedulerTaskState
from distributed.worker_state_machine import TaskStateState as WorkerTaskState
from models_library.projects_state import RunningState
from pydantic import BaseModel

DaskJobID: TypeAlias = str
DaskResources: TypeAlias = dict[str, int | float]

TASK_LIFE_CYCLE_EVENT: Final[str] = "task-lifecycle-{key}"
_SCHEDULER_TASK_STATE_TO_RUNNING_STATE: Final[
    dict[SchedulerTaskState, RunningState]
] = {
    "released": RunningState.NOT_STARTED,  # Known but not actively computing or in memory
    "waiting": RunningState.PENDING,  # On track to be computed, waiting on dependencies to arrive in memory
    "no-worker": RunningState.WAITING_FOR_RESOURCES,  # Ready to be computed, but no appropriate worker exists (for example because of resource restrictions, or because no worker is connected at all).
    "queued": RunningState.WAITING_FOR_RESOURCES,  # Ready to be computed, but all workers are already full.
    "processing": RunningState.PENDING,  # All dependencies are available and the task is assigned to a worker for compute (the scheduler doesn’t know whether it’s in a worker queue or actively being computed).
    "memory": RunningState.SUCCESS,  # In memory on one or more workers
    "erred": RunningState.FAILED,  # Task computation, or one of its dependencies, has encountered an error
    "forgotten": RunningState.UNKNOWN,  # Task is no longer needed by any client or dependent task, so it disappears from the scheduler as well. As soon as a task reaches this state, it is immediately dereferenced from the scheduler.
}

_WORKER_TASK_STATE_TO_RUNNING_STATE: Final[dict[WorkerTaskState, RunningState]] = {
    "cancelled": RunningState.ABORTED,  # The scheduler asked to forget about this task, but it’s technically impossible at the moment. See Task cancellation. The task can be found in whatever collections it was in its previous state.
    "constrained": RunningState.PENDING,  # Like ready, but the user specified resource constraints for this task. The task can be found in the WorkerState.constrained queue.
    "error": RunningState.FAILED,  # Task execution failed
    "executing": RunningState.STARTED,  # The task is currently being computed on a thread. It can be found in the WorkerState.executing set and in the distributed.worker.Worker.active_threads dict.
    "fetch": RunningState.PENDING,  # This task is in memory on one or more peer workers, but not on this worker. Its data is queued to be transferred over the network, either because it’s a dependency of a task in waiting state, or because the Active Memory Manager requested it to be replicated here. The task can be found in the WorkerState.data_needed heap.
    "flight": RunningState.PENDING,  # The task data is currently being transferred over the network from another worker. The task can be found in the WorkerState.in_flight_tasks and WorkerState.in_flight_workers collections.
    "forgotten": RunningState.UNKNOWN,  # The scheduler asked this worker to forget about the task, and there are neither dependents nor dependencies on the same worker.
    "long-running": RunningState.STARTED,  # Like executing, but the user code called distributed.secede() so the task no longer counts towards the maximum number of concurrent tasks. It can be found in the WorkerState.long_running set and in the distributed.worker.Worker.active_threads dict.
    "memory": RunningState.SUCCESS,  # Task execution completed, or the task was successfully transferred from another worker, and is now held in either WorkerState.data or WorkerState.actors.
    "missing": RunningState.PENDING,  # Like fetch, but all peer workers that were listed by the scheduler are either unreachable or have responded they don’t actually have the task data. The worker will periodically ask the scheduler if it knows of additional replicas; when it does, the task will transition again to fetch. The task can be found in the WorkerState.missing_dep_flight set.
    "ready": RunningState.PENDING,  # The task is ready to be computed; all of its dependencies are in memory on the current worker and it’s waiting for an available thread. The task can be found in the WorkerState.ready heap.
    "released": RunningState.PENDING,  # Known but not actively computing or in memory. A task can stay in this state when the scheduler asked to forget it, but it has dependent tasks on the same worker.
    "rescheduled": RunningState.PENDING,  # The task just raised the Reschedule exception. This is a transitory state, which is not stored permanently.
    "resumed": RunningState.PENDING,  # The task was recovered from cancelled state. See Task cancellation. The task can be found in whatever collections it was in its previous state.
    "waiting": RunningState.PENDING,  # The scheduler has added the task to the worker queue. All of its dependencies are in memory somewhere on the cluster, but not all of them are in memory on the current worker, so they need to be fetched.
}


class TaskLifeCycleState(BaseModel):
    key: str
    source: Literal["scheduler", "worker"]
    worker: str | None
    state: RunningState

    @classmethod
    def from_scheduler_task_state(
        cls, key: Key, worker: str | None, task_state: SchedulerTaskState
    ) -> "TaskLifeCycleState":
        return cls(
            key=f"{key!r}",
            source="scheduler",
            worker=worker,
            state=_SCHEDULER_TASK_STATE_TO_RUNNING_STATE[task_state],
        )

    @classmethod
    def from_worker_task_state(
        cls, key: Key, worker: str | None, task_state: WorkerTaskState
    ) -> "TaskLifeCycleState":
        return cls(
            key=f"{key!r}",
            source="worker",
            worker=worker,
            state=_WORKER_TASK_STATE_TO_RUNNING_STATE[task_state],
        )
