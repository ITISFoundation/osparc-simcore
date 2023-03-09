import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional, cast

import distributed
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    BaseTaskEvent,
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import TaskCancelEventName
from distributed.worker import get_worker
from distributed.worker_state_machine import TaskState

from .boot_mode import BootMode


def create_dask_worker_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"distributed.worker.{name}")


logger = create_dask_worker_logger(__name__)


def _get_current_task_state() -> Optional[TaskState]:
    worker = get_worker()
    logger.debug("current worker %s", f"{worker=}")
    current_task = worker.get_current_task()
    logger.debug("current task %s", f"{current_task=}")
    return worker.state.tasks.get(current_task)


def is_current_task_aborted() -> bool:
    task: Optional[TaskState] = _get_current_task_state()
    logger.debug("found following TaskState: %s", task)
    if task is None:
        # the task was removed from the list of tasks this worker should work on, meaning it is aborted
        # NOTE: this does not work in distributed mode, hence we need to use Events, Variables,or PubSub
        logger.debug("%s shall be aborted", f"{task=}")
        return True

    # NOTE: in distributed mode an event is necessary!
    cancel_event = distributed.Event(name=TaskCancelEventName.format(task.key))
    if cancel_event.is_set():
        logger.debug("%s shall be aborted", f"{task=}")
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


def get_current_task_resources() -> dict[str, Any]:
    if task := _get_current_task_state():
        if task_resources := task.resource_restrictions:
            return cast(dict[str, Any], task_resources)
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


@contextlib.asynccontextmanager
async def monitor_task_abortion(
    task_name: str, log_publisher: distributed.Pub
) -> AsyncIterator[None]:
    """This context manager periodically checks whether the client cancelled the
    monitored task. If that is the case, the monitored task will be cancelled (e.g.
    a asyncioCancelledError is raised in the task). The context manager will then
    raise a TaskCancelledError exception which will be propagated back to the client."""

    async def cancel_task(task_name: str) -> None:
        if task := next(
            (t for t in asyncio.all_tasks() if t.get_name() == task_name), None
        ):
            publish_event(
                log_publisher,
                TaskLogEvent.from_dask_worker(log="[sidecar] cancelling task..."),
            )
            logger.debug("cancelling %s....................", f"{task=}")
            task.cancel()

    async def periodicaly_check_if_aborted(task_name: str) -> None:
        while await asyncio.sleep(_TASK_ABORTION_INTERVAL_CHECK_S, result=True):
            logger.debug("checking if %s should be cancelled", f"{task_name=}")
            if is_current_task_aborted():
                await cancel_task(task_name)

    periodically_checking_task = None
    try:
        periodically_checking_task = asyncio.create_task(
            periodicaly_check_if_aborted(task_name),
            name=f"{task_name}_monitor_task_abortion",
        )

        yield
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
