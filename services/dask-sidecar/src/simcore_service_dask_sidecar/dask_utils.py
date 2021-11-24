import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager, suppress
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Dict, Optional, cast

import distributed
from dask_task_models_library.container_tasks.events import (
    BaseTaskEvent,
    TaskCancelEvent,
    TaskLogEvent,
    TaskProgressEvent,
)
from distributed.worker import TaskState, get_worker

from .boot_mode import BootMode


def create_dask_worker_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"distributed.worker.{name}")


logger = create_dask_worker_logger(__name__)


def _get_current_task_state() -> Optional[TaskState]:
    worker = get_worker()
    return worker.tasks.get(worker.get_current_task())


def is_current_task_aborted(sub: distributed.Sub) -> bool:
    task: Optional[TaskState] = _get_current_task_state()
    logger.debug("found following TaskState: %s", task)
    if task is None:
        # the task was removed from the list of tasks this worker should work on, meaning it is aborted
        # NOTE: this does not work in distributed mode, hence we need to use Variables,or PubSub
        return True

    with suppress(asyncio.TimeoutError):
        msg = sub.get(timeout="100ms")
        if msg:
            cancel_event = TaskCancelEvent.parse_raw(msg)  # type: ignore
            return bool(cancel_event.job_id == task.key)
    return False


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
            return cast(Dict[str, Any], task_resources)
    return {}


_TASK_ABORTION_INTERVAL_CHECK_S: int = 2


@asynccontextmanager
async def monitor_task_abortion(task_name: str) -> AsyncIterator[Awaitable[None]]:
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
            logger.debug(
                "starting task to check for task cancellation for task '%s'", task_name
            )
            sub = distributed.Sub(TaskCancelEvent.topic_name())
            while await asyncio.sleep(_TASK_ABORTION_INTERVAL_CHECK_S, result=True):
                logger.debug("checking if task should be cancelled")
                if is_current_task_aborted(sub):
                    logger.debug("Task was aborted. Cancelling fct [%s]...", task_name)
                    await cancel_task(task_name)
        except asyncio.CancelledError:
            pass

    periodically_checking_task = None
    try:
        periodically_checking_task = asyncio.create_task(
            perdiodicaly_check_if_aborted(task_name)
        )

        yield periodically_checking_task
    except asyncio.CancelledError:
        logger.warning("task '%s' was stopped through cancellation", task_name)
    finally:
        if periodically_checking_task:
            logger.debug(
                "cancelling task cancellation checker for task '%s'",
                task_name,
            )
            periodically_checking_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await periodically_checking_task


def publish_event(dask_pub: distributed.Pub, event: BaseTaskEvent) -> None:
    dask_pub.put(event.json())


class LogType(Enum):
    LOG = 1
    PROGRESS = 2
    INSTRUMENTATION = 3


def publish_task_logs(
    progress_pub: distributed.Pub,
    logs_pub: distributed.Pub,
    log_type: LogType,
    message_prefix: str,
    message: str,
) -> None:
    logger.info("[%s - %s]: %s", message_prefix, log_type.name, message)
    if log_type == LogType.PROGRESS:
        publish_event(
            progress_pub,
            TaskProgressEvent.from_dask_worker(progress=float(message)),
        )
    else:
        publish_event(logs_pub, TaskLogEvent.from_dask_worker(log=message))
