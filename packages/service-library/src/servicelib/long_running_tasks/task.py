import asyncio
import datetime
import inspect
import logging
import traceback
import urllib.parse
from collections import deque
from contextlib import suppress
from typing import Any, ClassVar, Final, Protocol, TypeAlias
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import PositiveFloat
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch

from ._store.base import BaseStore
from ._store.in_memory import InMemoryStore
from .errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskExceptionError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskNotRegisteredError,
)
from .models import TaskBase, TaskId, TaskStatus, TrackedTask

_logger = logging.getLogger(__name__)


# NOTE: for now only this one is used, in future it will be unqiue per service
# and this default will be removed and become mandatory
_DEFAULT_NAMESPACE: Final[str] = "lrt"

_CANCEL_TASK_TIMEOUT: Final[PositiveFloat] = datetime.timedelta(
    seconds=1
).total_seconds()

_CANCEL_TASKS_CHECK_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)

RegisteredTaskName: TypeAlias = str
Namespace: TypeAlias = str
TaskContext: TypeAlias = dict[str, Any]


class TaskProtocol(Protocol):
    async def __call__(
        self, progress: TaskProgress, *args: Any, **kwargs: Any
    ) -> Any: ...

    @property
    def __name__(self) -> str: ...


class TaskRegistry:
    REGISTERED_TASKS: ClassVar[dict[RegisteredTaskName, TaskProtocol]] = {}

    @classmethod
    def register(cls, task: TaskProtocol) -> None:
        cls.REGISTERED_TASKS[task.__name__] = task

    @classmethod
    def unregister(cls, task: TaskProtocol) -> None:
        if task.__name__ in cls.REGISTERED_TASKS:
            del cls.REGISTERED_TASKS[task.__name__]


async def _await_task(task: asyncio.Task) -> None:
    await task


async def _get_tasks_to_remove(
    tracked_tasks: BaseStore,
    stale_task_detect_timeout_s: PositiveFloat,
) -> list[TaskId]:
    utc_now = datetime.datetime.now(tz=datetime.UTC)

    tasks_to_remove: list[TaskId] = []

    for tracked_task in await tracked_tasks.list_tasks():
        if tracked_task.fire_and_forget:
            continue

        if tracked_task.last_status_check is None:
            # the task just added or never received a poll request
            elapsed_from_start = (utc_now - tracked_task.started).seconds
            if elapsed_from_start > stale_task_detect_timeout_s:
                tasks_to_remove.append(tracked_task.task_id)
        else:
            # the task status was already queried by the client
            elapsed_from_last_poll = (utc_now - tracked_task.last_status_check).seconds
            if elapsed_from_last_poll > stale_task_detect_timeout_s:
                tasks_to_remove.append(tracked_task.task_id)
    return tasks_to_remove


class TasksManager:
    """
    Monitors execution and results retrieval of a collection of asyncio.Tasks
    """

    def __init__(
        self,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
        namespace: Namespace = _DEFAULT_NAMESPACE,
        # TODO: inject a Redis connection
    ):
        self.namespace = namespace
        # Task groups: Every taskname maps to multiple asyncio.Task within TrackedTask model
        self._tracked_tasks: BaseStore = InMemoryStore()

        self.stale_task_check_interval = stale_task_check_interval
        self.stale_task_detect_timeout_s: PositiveFloat = (
            stale_task_detect_timeout.total_seconds()
        )

        self._stale_tasks_monitor_task: asyncio.Task | None = None
        self._cancelled_tasks_removal_task: asyncio.Task | None = None

    async def setup(self) -> None:
        self._stale_tasks_monitor_task = create_periodic_task(
            task=self._stale_tasks_monitor_worker,
            interval=self.stale_task_check_interval,
            task_name=f"{__name__}.{self._stale_tasks_monitor_worker.__name__}",
        )
        self._cancelled_tasks_removal_task = create_periodic_task(
            task=self._cancelled_tasks_removal_worker,
            interval=_CANCEL_TASKS_CHECK_INTERVAL,
            task_name=f"{__name__}.{self._cancelled_tasks_removal_worker.__name__}",
        )

    async def teardown(self) -> None:
        task_ids_to_remove: deque[TaskId] = deque()

        for tracked_task in await self._tracked_tasks.list_tasks():
            task_ids_to_remove.append(tracked_task.task_id)

        for task_id in task_ids_to_remove:
            # when closing we do not care about pending errors
            await self.remove_task(task_id, None, reraise_errors=False)

        if self._stale_tasks_monitor_task:
            with log_catch(_logger, reraise=False):
                await cancel_wait_task(
                    self._stale_tasks_monitor_task, max_delay=_CANCEL_TASK_TIMEOUT
                )

        if self._cancelled_tasks_removal_task:
            with log_catch(_logger, reraise=False):
                await cancel_wait_task(
                    self._cancelled_tasks_removal_task, max_delay=_CANCEL_TASK_TIMEOUT
                )

    async def _stale_tasks_monitor_worker(self) -> None:
        """
        A task is considered stale, if the task status is not queried
        in the last `stale_task_detect_timeout_s` and it is not a fire and forget type of task.

        This helps detect clients who:
        - started tasks and did not remove them
        - crashed without removing the task
        - did not fetch the result
        """
        # NOTE:
        # When a task has finished with a result or error and its
        # status is being polled it would appear that there is
        # an issue with the client.
        # Since we own the client, we assume (for now) this
        # will not be the case.

        tasks_to_remove = await _get_tasks_to_remove(
            self._tracked_tasks, self.stale_task_detect_timeout_s
        )

        # finally remove tasks and warn
        for task_id in tasks_to_remove:
            # NOTE: task can be in the following cases:
            # - still ongoing
            # - finished with a result
            # - finished with errors
            # we just print the status from where one can infer the above
            _logger.warning(
                "Removing stale task '%s' with status '%s'",
                task_id,
                (
                    await self.get_task_status(task_id, with_task_context=None)
                ).model_dump_json(),
            )
            await self.remove_task(
                task_id, with_task_context=None, reraise_errors=False
            )

    async def _cancelled_tasks_removal_worker(self) -> None:
        """
        tasks can be cancelled by the client, but they can run in differente processes
        once there is an entry in the cancelled store, attempt to cancel the task
        """

        for task_id in await self._tracked_tasks.get_cancelled():
            await self.remove_task(task_id, with_task_context=None)

    async def list_tasks(self, with_task_context: TaskContext | None) -> list[TaskBase]:
        if not with_task_context:
            return [
                TaskBase(task_id=task.task_id)
                for task in (await self._tracked_tasks.list_tasks())
            ]

        return [
            TaskBase(task_id=task.task_id)
            for task in (await self._tracked_tasks.list_tasks())
            if task.task_context == with_task_context
        ]

    async def _add_task(
        self,
        task: asyncio.Task,
        task_progress: TaskProgress,
        task_context: TaskContext,
        task_id: TaskId,
        *,
        fire_and_forget: bool,
    ) -> TrackedTask:

        tracked_task = TrackedTask(
            task_id=task_id,
            task=task,
            task_progress=task_progress,
            task_context=task_context,
            fire_and_forget=fire_and_forget,
        )
        await self._tracked_tasks.set_task(task_id, tracked_task)

        return tracked_task

    async def _get_tracked_task(
        self, task_id: TaskId, with_task_context: TaskContext | None
    ) -> TrackedTask:
        task = await self._tracked_tasks.get_task(task_id)

        if task is None:
            raise TaskNotFoundError(task_id=task_id)

        if with_task_context and task.task_context != with_task_context:
            raise TaskNotFoundError(task_id=task_id)

        return task

    async def get_task_status(
        self, task_id: TaskId, with_task_context: TaskContext | None
    ) -> TaskStatus:
        """
        returns: the status of the task, along with updates
        form the progress

        raises TaskNotFoundError if the task cannot be found
        """
        tracked_task: TrackedTask = await self._get_tracked_task(
            task_id, with_task_context
        )
        tracked_task.last_status_check = datetime.datetime.now(tz=datetime.UTC)

        task = tracked_task.task
        done = task.done()

        return TaskStatus.model_validate(
            {
                "task_progress": tracked_task.task_progress,
                "done": done,
                "started": tracked_task.started,
            }
        )

    async def get_task_result(
        self, task_id: TaskId, with_task_context: TaskContext | None
    ) -> Any:
        """
        returns: the result of the task

        raises TaskNotFoundError if the task cannot be found
        raises TaskCancelledError if the task was cancelled
        raises TaskNotCompletedError if the task is not completed
        """
        tracked_task = await self._get_tracked_task(task_id, with_task_context)

        try:
            return tracked_task.task.result()
        except asyncio.InvalidStateError as exc:
            # the task is not ready
            raise TaskNotCompletedError(task_id=task_id) from exc
        except asyncio.CancelledError as exc:
            # the task was cancelled
            raise TaskCancelledError(task_id=task_id) from exc

    async def cancel_task(
        self, task_id: TaskId, with_task_context: TaskContext | None
    ) -> None:
        """
        cancels the task

        raises TaskNotFoundError if the task cannot be found
        """
        await self._tracked_tasks.set_as_cancelled(task_id)
        tracked_task = await self._get_tracked_task(task_id, with_task_context)
        await self._cancel_tracked_task(tracked_task.task, task_id, reraise_errors=True)

    @staticmethod
    async def _cancel_asyncio_task(
        task: asyncio.Task, reference: str, *, reraise_errors: bool
    ) -> None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            try:
                try:
                    await asyncio.wait_for(
                        _await_task(task), timeout=_CANCEL_TASK_TIMEOUT
                    )
                except TimeoutError:
                    _logger.warning(
                        "Timed out while awaiting for cancellation of '%s'", reference
                    )
            except Exception:  # pylint:disable=broad-except
                if reraise_errors:
                    raise

    async def _cancel_tracked_task(
        self, task: asyncio.Task, task_id: TaskId, *, reraise_errors: bool
    ) -> None:
        try:
            await self._cancel_asyncio_task(
                task, task_id, reraise_errors=reraise_errors
            )
        except Exception as e:  # pylint:disable=broad-except
            formatted_traceback = "".join(traceback.format_exception(e))
            raise TaskExceptionError(
                task_id=task_id, exception=e, traceback=formatted_traceback
            ) from e

    async def remove_task(
        self,
        task_id: TaskId,
        with_task_context: TaskContext | None,
        *,
        reraise_errors: bool = True,
    ) -> None:
        """cancels and removes task"""
        try:
            tracked_task = await self._get_tracked_task(task_id, with_task_context)
        except TaskNotFoundError:
            if reraise_errors:
                raise
            return
        try:
            await self._cancel_tracked_task(
                tracked_task.task, task_id, reraise_errors=reraise_errors
            )
        finally:
            await self._tracked_tasks.delete_task(task_id)

    def _get_task_id(self, task_name: str, *, is_unique: bool) -> TaskId:
        unique_part = "unique" if is_unique else f"{uuid4()}"
        return f"{self.namespace}.{task_name}.{unique_part}"

    async def start_task(
        self,
        registered_task_name: RegisteredTaskName,
        *,
        unique: bool,
        task_context: TaskContext | None,
        task_name: str | None,
        fire_and_forget: bool,
        **task_kwargs: Any,
    ) -> TaskId:
        if registered_task_name not in TaskRegistry.REGISTERED_TASKS:
            raise TaskNotRegisteredError(task_name=registered_task_name)

        task = TaskRegistry.REGISTERED_TASKS[registered_task_name]

        # NOTE: If not task name is given, it will be composed of the handler's module and it's name
        # to keep the urls shorter and more meaningful.
        handler_module = inspect.getmodule(task)
        handler_module_name = handler_module.__name__ if handler_module else ""
        task_name = task_name or f"{handler_module_name}.{task.__name__}"
        task_name = urllib.parse.quote(task_name, safe="")

        task_id = self._get_task_id(task_name, is_unique=unique)

        # only one unique task can be running
        queried_task = await self._tracked_tasks.get_task(task_id)
        if unique and queried_task is not None:
            raise TaskAlreadyRunningError(
                task_name=task_name, managed_task=queried_task
            )

        task_progress = TaskProgress.create(task_id=task_id)

        # bind the task with progress 0 and 1
        async def _progress_task(progress: TaskProgress, handler: TaskProtocol):
            progress.update(message="starting", percent=0)
            try:
                return await handler(progress, **task_kwargs)
            finally:
                progress.update(message="finished", percent=1)

        async_task = asyncio.create_task(
            _progress_task(task_progress, task), name=task_name
        )

        tracked_task = await self._add_task(
            task=async_task,
            task_progress=task_progress,
            task_context=task_context or {},
            fire_and_forget=fire_and_forget,
            task_id=task_id,
        )

        return tracked_task.task_id


__all__: tuple[str, ...] = (
    "TaskAlreadyRunningError",
    "TaskCancelledError",
    "TaskId",
    "TaskProgress",
    "TaskProtocol",
    "TaskStatus",
    "TasksManager",
    "TrackedTask",
)
