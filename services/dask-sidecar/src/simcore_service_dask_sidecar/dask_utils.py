import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Final

import distributed
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    BaseTaskEvent,
    TaskLogEvent,
    TaskProgressEvent,
)
from dask_task_models_library.container_tasks.io import TaskCancelEventName
from dask_task_models_library.container_tasks.protocol import TaskOwner
from distributed.worker import get_worker
from distributed.worker_state_machine import TaskState
from models_library.progress_bar import ProgressReport
from servicelib.logging_utils import LogLevelInt, LogMessageStr, log_catch

_logger = logging.getLogger(__name__)


def _get_current_task_state() -> TaskState | None:
    worker = get_worker()
    _logger.debug("current worker %s", f"{worker=}")
    current_task = worker.get_current_task()
    _logger.debug("current task %s", f"{current_task=}")
    return worker.state.tasks.get(current_task)


def is_current_task_aborted() -> bool:
    task: TaskState | None = _get_current_task_state()
    _logger.debug("found following TaskState: %s", task)
    if task is None:
        # the task was removed from the list of tasks this worker should work on, meaning it is aborted
        # NOTE: this does not work in distributed mode, hence we need to use Events, Variables,or PubSub
        _logger.debug("%s shall be aborted", f"{task=}")
        return True

    # NOTE: in distributed mode an event is necessary!
    cancel_event = distributed.Event(name=TaskCancelEventName.format(task.key))
    if cancel_event.is_set():
        _logger.debug("%s shall be aborted", f"{task=}")
        return True
    return False


_DEFAULT_MAX_RESOURCES: Final[dict[str, float]] = {"CPU": 1, "RAM": 1024**3}


def get_current_task_resources() -> dict[str, float]:
    current_task_resources = _DEFAULT_MAX_RESOURCES
    if task := _get_current_task_state():
        if task_resources := task.resource_restrictions:
            current_task_resources.update(task_resources)
    return current_task_resources


@dataclass(slots=True, kw_only=True)
class TaskPublisher:
    task_owner: TaskOwner
    progress: distributed.Pub = field(init=False)
    _last_published_progress_value: float = -1
    logs: distributed.Pub = field(init=False)

    def __post_init__(self) -> None:
        self.progress = distributed.Pub(TaskProgressEvent.topic_name())
        self.logs = distributed.Pub(TaskLogEvent.topic_name())

    def publish_progress(self, report: ProgressReport) -> None:
        rounded_value = round(report.percent_value, ndigits=2)
        if rounded_value > self._last_published_progress_value:
            with log_catch(logger=_logger, reraise=False):
                publish_event(
                    self.progress,
                    TaskProgressEvent.from_dask_worker(
                        progress=rounded_value, task_owner=self.task_owner
                    ),
                )
                self._last_published_progress_value = rounded_value
            _logger.debug("PROGRESS: %s", rounded_value)

    def publish_logs(
        self,
        *,
        message: LogMessageStr,
        log_level: LogLevelInt,
    ) -> None:
        with log_catch(logger=_logger, reraise=False):
            publish_event(
                self.logs,
                TaskLogEvent.from_dask_worker(
                    log=message, log_level=log_level, task_owner=self.task_owner
                ),
            )
        _logger.log(log_level, message)


_TASK_ABORTION_INTERVAL_CHECK_S: int = 2


@contextlib.asynccontextmanager
async def monitor_task_abortion(
    task_name: str, task_publishers: TaskPublisher
) -> AsyncIterator[None]:
    """This context manager periodically checks whether the client cancelled the
    monitored task. If that is the case, the monitored task will be cancelled (e.g.
    a asyncioCancelledError is raised in the task). The context manager will then
    raise a TaskCancelledError exception which will be propagated back to the client."""

    async def cancel_task(task_name: str) -> None:
        if task := next(
            (t for t in asyncio.all_tasks() if t.get_name() == task_name), None
        ):
            task_publishers.publish_logs(
                message="[sidecar] cancelling task...", log_level=logging.INFO
            )
            task.cancel()

    async def periodicaly_check_if_aborted(task_name: str) -> None:
        while await asyncio.sleep(_TASK_ABORTION_INTERVAL_CHECK_S, result=True):
            _logger.debug("checking if %s should be cancelled", f"{task_name=}")
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
        task_publishers.publish_logs(
            message="[sidecar] task run was aborted", log_level=logging.INFO
        )

        raise TaskCancelledError from exc
    finally:
        if periodically_checking_task:
            _logger.debug(
                "cancelling task cancellation checker for task '%s'",
                task_name,
            )
            periodically_checking_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await periodically_checking_task


def publish_event(dask_pub: distributed.Pub, event: BaseTaskEvent) -> None:
    """never reraises, only CancellationError"""
    with log_catch(_logger, reraise=False):
        dask_pub.put(event.model_dump_json())
