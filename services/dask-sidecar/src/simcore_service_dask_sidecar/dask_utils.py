from typing import Optional

from dask_task_models_library.container_tasks.events import TaskEvent
from distributed import Pub
from distributed.worker import TaskState, get_worker

from .boot_mode import BootMode


def _get_current_task_state() -> Optional[TaskState]:
    worker = get_worker()
    return worker.tasks.get(worker.get_current_task())


def publish_event(dask_pub: Pub, event: TaskEvent) -> None:
    dask_pub.put(event.json())


def is_current_task_aborted() -> bool:
    task: Optional[TaskState] = _get_current_task_state()
    # the task was removed from the list of tasks this worker should work on, meaning it is aborted
    return task is None


def get_current_task_boot_mode() -> BootMode:
    task: Optional[TaskState] = _get_current_task_state()
    if task and task.resource_restrictions:
        if task.resource_restrictions.get("MPI", 0) > 0:
            return BootMode.MPI
        if task.resource_restrictions.get("GPU", 0) > 0:
            return BootMode.GPU
    return BootMode.CPU
