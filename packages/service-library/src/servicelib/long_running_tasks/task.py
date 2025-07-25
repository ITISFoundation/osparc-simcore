import asyncio
import datetime
import functools
import inspect
import logging
import traceback
import urllib.parse
from contextlib import suppress
from typing import Any, ClassVar, Final, Protocol, TypeAlias
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import PositiveFloat
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis import RedisClientSDK, exclusive
from ._store.base import BaseStore
from ._store.redis import RedisStore
from .errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskExceptionError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskNotRegisteredError,
)
from .models import TaskBase, TaskContext, TaskData, TaskId, TaskStatus

_logger = logging.getLogger(__name__)


_CANCEL_TASK_TIMEOUT: Final[PositiveFloat] = datetime.timedelta(
    seconds=10  # NOTE: 1 second is too short to cleanup a task
).total_seconds()

_CANCEL_TASKS_CHECK_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)


RegisteredTaskName: TypeAlias = str
Namespace: TypeAlias = str


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
) -> list[tuple[TaskId, TaskContext]]:
    utc_now = datetime.datetime.now(tz=datetime.UTC)

    tasks_to_remove: list[tuple[TaskId, TaskContext]] = []

    for tracked_task in await tracked_tasks.list_tasks_data():
        if tracked_task.fire_and_forget:
            continue

        if tracked_task.last_status_check is None:
            # the task just added or never received a poll request
            elapsed_from_start = (utc_now - tracked_task.started).seconds
            if elapsed_from_start > stale_task_detect_timeout_s:
                tasks_to_remove.append(
                    (tracked_task.task_id, tracked_task.task_context)
                )
        else:
            # the task status was already queried by the client
            elapsed_from_last_poll = (utc_now - tracked_task.last_status_check).seconds
            if elapsed_from_last_poll > stale_task_detect_timeout_s:
                tasks_to_remove.append(
                    (tracked_task.task_id, tracked_task.task_context)
                )
    return tasks_to_remove


class TasksManager:
    """
    Monitors execution and results retrieval of a collection of asyncio.Tasks
    """

    def __init__(
        self,
        redis_settings: RedisSettings,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
        namespace: Namespace,
    ):
        # Task groups: Every taskname maps to multiple asyncio.Task within TrackedTask model
        self._tasks_data: BaseStore = RedisStore(redis_settings, namespace)
        self._created_tasks: dict[TaskId, asyncio.Task] = {}

        self.stale_task_check_interval = stale_task_check_interval
        self.stale_task_detect_timeout_s: PositiveFloat = (
            stale_task_detect_timeout.total_seconds()
        )
        self.namespace = namespace
        self.redis_settings = redis_settings

        self._stale_tasks_monitor_task: asyncio.Task | None = None
        self._cancelled_tasks_removal_task: asyncio.Task | None = None
        self.redis_client_sdk: RedisClientSDK | None = None

    async def setup(self) -> None:
        await self._tasks_data.setup()

        self.redis_client_sdk = RedisClientSDK(
            self.redis_settings.build_redis_dsn(RedisDatabase.LOCKS),
            client_name=f"long_running_tasks_store_{self.namespace}_lock",
        )
        await self.redis_client_sdk.setup()

        self._stale_tasks_monitor_task = create_periodic_task(
            task=exclusive(
                self.redis_client_sdk,
                lock_key=f"{__name__}_{self.namespace}_stale_tasks_monitor",
            )(self._stale_tasks_monitor_worker),
            interval=self.stale_task_check_interval,
            task_name=f"{__name__}.{self._stale_tasks_monitor_worker.__name__}",
        )
        self._cancelled_tasks_removal_task = create_periodic_task(
            task=self._cancelled_tasks_removal_worker,
            interval=_CANCEL_TASKS_CHECK_INTERVAL,
            task_name=f"{__name__}.{self._cancelled_tasks_removal_worker.__name__}",
        )

    async def teardown(self) -> None:
        for tracked_task in await self._tasks_data.list_tasks_data():
            # when closing we do not care about pending errors
            await self.remove_task(
                tracked_task.task_id, tracked_task.task_context, reraise_errors=False
            )

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

        if self.redis_client_sdk is not None:
            await self.redis_client_sdk.shutdown()

        await self._tasks_data.shutdown()

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
            self._tasks_data, self.stale_task_detect_timeout_s
        )

        # finally remove tasks and warn
        for task_id, task_context in tasks_to_remove:
            # NOTE: task can be in the following cases:
            # - still ongoing
            # - finished with a result
            # - finished with errors
            # we just print the status from where one can infer the above
            _logger.warning(
                "Removing stale task '%s' with status '%s'",
                task_id,
                (
                    await self.get_task_status(task_id, with_task_context=task_context)
                ).model_dump_json(),
            )
            await self.remove_task(
                task_id, with_task_context=task_context, reraise_errors=False
            )

    async def _cancelled_tasks_removal_worker(self) -> None:
        """
        tasks can be cancelled by the client, but they can run in differente processes
        once there is an entry in the cancelled store, attempt to cancel the task
        """

        for task_id, task_context in (await self._tasks_data.get_cancelled()).items():
            await self.remove_task(task_id, task_context)

    async def list_tasks(self, with_task_context: TaskContext | None) -> list[TaskBase]:
        if not with_task_context:
            return [
                TaskBase(task_id=task.task_id)
                for task in (await self._tasks_data.list_tasks_data())
            ]

        return [
            TaskBase(task_id=task.task_id)
            for task in (await self._tasks_data.list_tasks_data())
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
    ) -> TaskData:

        task_data = TaskData(
            task_id=task_id,
            task_progress=task_progress,
            task_context=task_context,
            fire_and_forget=fire_and_forget,
        )
        await self._tasks_data.set_task_data(task_id, task_data)
        self._created_tasks[task_id] = task

        return task_data

    async def _get_tracked_task(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> TaskData:
        task_data = await self._tasks_data.get_task_data(task_id)

        if task_data is None:
            raise TaskNotFoundError(task_id=task_id)

        if with_task_context and task_data.task_context != with_task_context:
            raise TaskNotFoundError(task_id=task_id)

        return task_data

    async def get_task_status(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> TaskStatus:
        """
        returns: the status of the task, along with updates
        form the progress

        raises TaskNotFoundError if the task cannot be found
        """
        task_data: TaskData = await self._get_tracked_task(task_id, with_task_context)
        task_data.last_status_check = datetime.datetime.now(tz=datetime.UTC)
        await self._tasks_data.set_task_data(task_id, task_data)

        task = self._created_tasks[task_id]
        done = task.done()

        return TaskStatus.model_validate(
            {
                "task_progress": task_data.task_progress,
                "done": done,
                "started": task_data.started,
            }
        )

    async def get_task_result(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> Any:
        """
        returns: the result of the task

        raises TaskNotFoundError if the task cannot be found
        raises TaskCancelledError if the task was cancelled
        raises TaskNotCompletedError if the task is not completed
        """
        tracked_task = await self._get_tracked_task(task_id, with_task_context)

        try:
            return self._created_tasks[tracked_task.task_id].result()
        except asyncio.InvalidStateError as exc:
            # the task is not ready
            raise TaskNotCompletedError(task_id=task_id) from exc
        except asyncio.CancelledError as exc:
            # the task was cancelled
            raise TaskCancelledError(task_id=task_id) from exc

    async def cancel_task(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> None:
        """
        cancels the task

        raises TaskNotFoundError if the task cannot be found
        """
        await self._tasks_data.set_as_cancelled(task_id, with_task_context)
        tracked_task = await self._get_tracked_task(task_id, with_task_context)
        await self._cancel_tracked_task(
            self._created_tasks[tracked_task.task_id], task_id, reraise_errors=True
        )

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
        with_task_context: TaskContext,
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
                self._created_tasks[tracked_task.task_id],
                task_id,
                reraise_errors=reraise_errors,
            )
        finally:
            await self._tasks_data.delete_task_data(task_id)
            del self._created_tasks[tracked_task.task_id]

    def _get_task_id(self, task_name: str, *, is_unique: bool) -> TaskId:
        unique_part = "unique" if is_unique else f"{uuid4()}"
        return f"{self.namespace}.{task_name}.{unique_part}"

    async def _update_progress(
        self,
        task_id: TaskId,
        task_context: TaskContext,
        task_progress: TaskProgress,
    ) -> None:
        tracked_data = await self._get_tracked_task(task_id, task_context)
        tracked_data.task_progress = task_progress
        await self._tasks_data.set_task_data(task_id=task_id, value=tracked_data)

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
        queried_task = await self._tasks_data.get_task_data(task_id)
        if unique and queried_task is not None:
            raise TaskAlreadyRunningError(
                task_name=task_name, managed_task=queried_task
            )

        context_to_use = task_context or {}
        task_progress = TaskProgress.create(task_id=task_id)
        # set update callback
        task_progress.set_update_callback(
            functools.partial(self._update_progress, task_id, context_to_use)
        )

        # bind the task with progress 0 and 1
        async def _progress_task(progress: TaskProgress, handler: TaskProtocol):
            await progress.update(message="starting", percent=0)
            try:
                return await handler(progress, **task_kwargs)
            finally:
                await progress.update(message="finished", percent=1)

        async_task = asyncio.create_task(
            _progress_task(task_progress, task), name=task_name
        )

        tracked_task = await self._add_task(
            task=async_task,
            task_progress=task_progress,
            task_context=context_to_use,
            fire_and_forget=fire_and_forget,
            task_id=task_id,
        )

        return tracked_task.task_id


__all__: tuple[str, ...] = (
    "TaskAlreadyRunningError",
    "TaskCancelledError",
    "TaskData",
    "TaskId",
    "TaskProgress",
    "TaskProtocol",
    "TaskStatus",
    "TasksManager",
)
