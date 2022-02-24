import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Dict, Optional, cast

import distributed
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    BaseTaskEvent,
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from distributed.worker import TaskState, get_worker

from .boot_mode import BootMode


def create_dask_worker_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"distributed.worker.{name}")


logger = create_dask_worker_logger(__name__)


def _get_current_task_state() -> Optional[TaskState]:
    worker = get_worker()
    logger.debug("current worker %s", f"{worker=}")
    current_task = worker.get_current_task()
    logger.debug("current task %s", f"{current_task=}")
    return worker.tasks.get(current_task)


def is_current_task_aborted() -> bool:
    task: Optional[TaskState] = _get_current_task_state()
    logger.debug("found following TaskState: %s", task)
    if task is None:
        # the task was removed from the list of tasks this worker should work on, meaning it is aborted
        # NOTE: this does not work in distributed mode, hence we need to use Events, Variables,or PubSub
        return True

    # NOTE: in distributed mode an event is necessary!
    cancel_event = distributed.Event(name=task.key)
    if cancel_event.is_set():
        return True
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


@dataclass()
class TaskPublisher:
    state: distributed.Pub = field(init=False)
    progress: distributed.Pub = field(init=False)
    logs: distributed.Pub = field(init=False)

    def __post_init__(self):
        self.state = distributed.Pub(TaskStateEvent.topic_name())
        self.progress = distributed.Pub(TaskProgressEvent.topic_name())
        self.logs = distributed.Pub(TaskLogEvent.topic_name())


_TASK_ABORTION_INTERVAL_CHECK_S: int = 2


@asynccontextmanager
async def monitor_task_abortion(
    task_name: str, log_publisher: distributed.Pub
) -> AsyncIterator[Awaitable[None]]:
    async def cancel_task(task_name: str) -> None:
        tasks = asyncio.all_tasks()
        logger.debug("running tasks: %s", tasks)
        for task in tasks:
            if task.get_name() == task_name:
                publish_event(
                    log_publisher,
                    TaskLogEvent.from_dask_worker(log="[sidecar] cancelling task..."),
                )
                logger.debug("canceling %s....................", f"{task=}")
                task.cancel()
                break

    async def periodicaly_check_if_aborted(task_name: str) -> None:
        try:
            logger.debug(
                "starting task to check for task cancellation for '%s'", f"{task_name=}"
            )
            while await asyncio.sleep(_TASK_ABORTION_INTERVAL_CHECK_S, result=True):
                logger.debug("checking if task should be cancelled")
                if is_current_task_aborted():
                    logger.debug(
                        "Task was aborted. Cancelling fct [%s]...", f"{task_name=}"
                    )
                    await cancel_task(task_name)
        except asyncio.CancelledError:
            pass

    periodically_checking_task = None
    try:
        periodically_checking_task = asyncio.create_task(
            periodicaly_check_if_aborted(task_name)
        )

        yield periodically_checking_task
    except asyncio.CancelledError as exc:
        publish_event(
            log_publisher,
            TaskLogEvent.from_dask_worker(log="[sidecar] task run was aborted"),
        )
        raise TaskCancelledError from exc
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
