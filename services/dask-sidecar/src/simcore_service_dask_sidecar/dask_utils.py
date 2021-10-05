import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Dict, Optional

from dask_task_models_library.container_tasks.events import TaskEvent
from distributed import Pub
from distributed.worker import TaskState, get_worker

from .boot_mode import BootMode


def _get_current_task_state() -> Optional[TaskState]:
    worker = get_worker()
    return worker.tasks.get(worker.get_current_task())


def create_dask_worker_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"distributed.worker.{name}")


logger = create_dask_worker_logger(__name__)


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


def get_current_task_resources() -> Dict[str, Any]:
    if task := _get_current_task_state():
        if task_resources := task.resource_restrictions:
            return task_resources
    return {}


@asynccontextmanager
async def MonitorTaskAbortion(task_name: str) -> AsyncIterator[Awaitable[None]]:
    async def cancel_task(task_name: str) -> None:
        tasks = asyncio.all_tasks()
        logger.debug("running tasks: %s", tasks)
        for task in tasks:
            if task.get_name() == task_name:
                logger.info("canceling task %s....................", task)
                task.cancel()
                break

    async def perdiodicaly_check_if_aborted(task_name: str) -> None:
        try:
            while await asyncio.sleep(5, result=True):
                if is_current_task_aborted():
                    logger.info("Task was aborted. Cancelling fct [%s]...", task_name)
                    asyncio.get_event_loop().call_soon(cancel_task, task_name)
        except asyncio.CancelledError:
            pass

    periodically_checking_task = None
    try:
        periodically_checking_task = asyncio.create_task(
            perdiodicaly_check_if_aborted(task_name)
        )

        yield periodically_checking_task
    finally:
        if periodically_checking_task:
            periodically_checking_task.cancel()
