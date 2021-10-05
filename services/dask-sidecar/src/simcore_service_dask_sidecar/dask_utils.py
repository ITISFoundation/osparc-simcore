from typing import Optional

from dask_task_models_library.container_tasks.events import TaskEvent
from distributed import Pub
from distributed.worker import TaskState, get_worker

from .boot_mode import BootMode


def publish_event(dask_pub: Pub, event: TaskEvent) -> None:
    dask_pub.put(event.json())


def get_task_state() -> Optional[TaskState]:
    worker = get_worker()
    return worker.tasks.get(worker.get_current_task())


def is_task_aborted() -> bool:
    task: Optional[TaskState] = get_task_state()
    # the task was removed from the list of tasks this worker should work on, meaning it is aborted
    return task is None


def get_task_boot_mode(task: Optional[TaskState]) -> BootMode:
    if not task or not task.resource_restrictions:
        return BootMode.CPU
    if task.resource_restrictions.get("MPI", 0) > 0:
        return BootMode.MPI
    if task.resource_restrictions.get("GPU", 0) > 0:
        return BootMode.GPU
    return BootMode.CPU
