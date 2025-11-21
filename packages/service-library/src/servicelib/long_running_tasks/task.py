import asyncio
import datetime
import functools
import inspect
import logging
import urllib.parse
from contextlib import suppress
from typing import Any, ClassVar, Final, Protocol, TypeAlias
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import NonNegativeFloat, PositiveFloat
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity import (
    AsyncRetrying,
    retry_unless_exception_type,
    stop_after_delay,
    wait_exponential,
)

from ..background_task import create_periodic_task
from ..logging_utils import log_catch, log_context
from ..redis import RedisClientSDK, exclusive
from ..utils import limited_gather
from ._redis_store import RedisStore
from ._serialization import dumps
from .errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskNotRegisteredError,
    TaskRaisedUnserializableError,
)
from .models import (
    LRTNamespace,
    RegisteredTaskName,
    ResultField,
    TaskBase,
    TaskContext,
    TaskData,
    TaskId,
    TaskStatus,
)

_logger = logging.getLogger(__name__)


_CANCEL_TASKS_CHECK_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)
_STATUS_UPDATE_CHECK_INTERNAL: Final[datetime.timedelta] = datetime.timedelta(seconds=1)
_MAX_EXCLUSIVE_TASK_CANCEL_TIMEOUT: Final[NonNegativeFloat] = 5
_TASK_REMOVAL_MAX_WAIT: Final[NonNegativeFloat] = 60
_PARALLEL_TASKS_CANCELLATION: Final[int] = 5

AllowedErrrors: TypeAlias = tuple[type[BaseException], ...]


class TaskProtocol(Protocol):
    async def __call__(
        self, progress: TaskProgress, *args: Any, **kwargs: Any
    ) -> Any: ...

    @property
    def __name__(self) -> str: ...


class TaskRegistry:
    _REGISTERED_TASKS: ClassVar[
        dict[RegisteredTaskName, tuple[AllowedErrrors, TaskProtocol]]
    ] = {}

    @classmethod
    def register(
        cls,
        task: TaskProtocol,
        allowed_errors: AllowedErrrors = (),
        **partial_kwargs,
    ) -> None:
        partial_task = functools.partial(task, **partial_kwargs)
        # allows to call the partial via it's original name
        partial_task.__name__ = task.__name__  # type: ignore[attr-defined]
        cls._REGISTERED_TASKS[task.__name__] = [allowed_errors, partial_task]  # type: ignore[assignment]

    @classmethod
    def get_registered_tasks(
        cls,
    ) -> dict[RegisteredTaskName, tuple[AllowedErrrors, TaskProtocol]]:
        return cls._REGISTERED_TASKS

    @classmethod
    def get_task(cls, task_name: RegisteredTaskName) -> TaskProtocol:
        return cls._REGISTERED_TASKS[task_name][1]

    @classmethod
    def get_allowed_errors(cls, task_name: RegisteredTaskName) -> AllowedErrrors:
        return cls._REGISTERED_TASKS[task_name][0]

    @classmethod
    def unregister(cls, task: TaskProtocol) -> None:
        if task.__name__ in cls._REGISTERED_TASKS:
            del cls._REGISTERED_TASKS[task.__name__]


async def _get_tasks_to_remove(
    tracked_tasks: RedisStore,
    stale_task_detect_timeout_s: PositiveFloat,
) -> list[tuple[TaskId, TaskContext]]:
    utc_now = datetime.datetime.now(tz=datetime.UTC)

    tasks_to_remove: list[tuple[TaskId, TaskContext]] = []

    for tracked_task in await tracked_tasks.list_tasks_data():
        if tracked_task.fire_and_forget:
            # fire and forget tasks also need to be remove from tracking
            # when detectes as done, start counting how much time has elapsed
            # if over stale_task_detect_timeout_s remove the task

            # wait for task to complete
            if not tracked_task.is_done:
                continue

            # mark detected as done
            if tracked_task.detected_as_done_at is None:
                await tracked_tasks.update_task_data(
                    tracked_task.task_id,
                    updates={
                        "detected_as_done_at": datetime.datetime.now(tz=datetime.UTC)
                    },
                )
                continue

            # if enough time passes remove the task
            elapsed_since_done = (
                utc_now - tracked_task.detected_as_done_at
            ).total_seconds()
            if elapsed_since_done > stale_task_detect_timeout_s:
                tasks_to_remove.append(
                    (tracked_task.task_id, tracked_task.task_context)
                )
                continue

        if tracked_task.last_status_check is None:
            # the task just added or never received a poll request
            elapsed_from_start = (utc_now - tracked_task.started).total_seconds()
            if elapsed_from_start > stale_task_detect_timeout_s:
                tasks_to_remove.append(
                    (tracked_task.task_id, tracked_task.task_context)
                )
        else:
            # the task status was already queried by the client
            elapsed_from_last_poll = (
                utc_now - tracked_task.last_status_check
            ).total_seconds()
            if elapsed_from_last_poll > stale_task_detect_timeout_s:
                tasks_to_remove.append(
                    (tracked_task.task_id, tracked_task.task_context)
                )
    return tasks_to_remove


class TasksManager:  # pylint:disable=too-many-instance-attributes
    """
    Monitors execution and results retrieval of a collection of asyncio.Tasks
    """

    def __init__(
        self,
        redis_settings: RedisSettings,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
        lrt_namespace: LRTNamespace,
    ):
        # Task groups: Every taskname maps to multiple asyncio.Task within TrackedTask model
        self._tasks_data = RedisStore(redis_settings, lrt_namespace)
        self._created_tasks: dict[TaskId, asyncio.Task] = {}

        self.stale_task_check_interval = stale_task_check_interval
        self.stale_task_detect_timeout_s: PositiveFloat = (
            stale_task_detect_timeout.total_seconds()
        )
        self.lrt_namespace = lrt_namespace
        self.redis_settings = redis_settings

        self.locks_redis_client_sdk: RedisClientSDK | None = None

        # stale_tasks_monitor
        self._task_stale_tasks_monitor: asyncio.Task | None = None
        self._started_event_task_stale_tasks_monitor = asyncio.Event()

        # cancelled_tasks_removal
        self._task_cancelled_tasks_removal: asyncio.Task | None = None
        self._started_event_task_cancelled_tasks_removal = asyncio.Event()

        # tasks_monitor
        self._task_tasks_monitor: asyncio.Task | None = None
        self._started_event_task_tasks_monitor = asyncio.Event()

    async def setup(self) -> None:
        await self._tasks_data.setup()

        self.locks_redis_client_sdk = RedisClientSDK(
            self.redis_settings.build_redis_dsn(RedisDatabase.LOCKS),
            client_name=f"{__name__}_{self.lrt_namespace}_lock",
        )
        await self.locks_redis_client_sdk.setup()

        # stale_tasks_monitor
        self._task_stale_tasks_monitor = create_periodic_task(
            task=exclusive(
                self.locks_redis_client_sdk,
                lock_key=f"{__name__}_{self.lrt_namespace}_stale_tasks_monitor",
            )(self._stale_tasks_monitor),
            interval=self.stale_task_check_interval,
            task_name=f"{__name__}.{self._stale_tasks_monitor.__name__}",
        )
        await self._started_event_task_stale_tasks_monitor.wait()

        # cancelled_tasks_removal
        self._task_cancelled_tasks_removal = create_periodic_task(
            task=self._cancelled_tasks_removal,
            interval=_CANCEL_TASKS_CHECK_INTERVAL,
            task_name=f"{__name__}.{self._cancelled_tasks_removal.__name__}",
        )
        await self._started_event_task_cancelled_tasks_removal.wait()

        # tasks_monitor
        self._task_tasks_monitor = create_periodic_task(
            task=self._tasks_monitor,
            interval=_STATUS_UPDATE_CHECK_INTERNAL,
            task_name=f"{__name__}.{self._tasks_monitor.__name__}",
        )
        await self._started_event_task_tasks_monitor.wait()

    async def teardown(self) -> None:
        # stop cancelled_tasks_removal
        if self._task_cancelled_tasks_removal:
            await cancel_wait_task(self._task_cancelled_tasks_removal)

        # stopping only tasks that are handled by this manager
        # otherwise it will cancel long running tasks that were running in diffierent processes
        async def _remove_local_task(task_data: TaskData) -> None:
            with log_catch(_logger, reraise=False):
                await self.remove_task(
                    task_data.task_id,
                    task_data.task_context,
                    wait_for_removal=False,
                )
                await self._attempt_to_remove_local_task(task_data.task_id)

        await limited_gather(
            *[
                _remove_local_task(tracked_task)
                for task_id in self._created_tasks
                if (tracked_task := await self._tasks_data.get_task_data(task_id))
                is not None
            ],
            log=_logger,
            limit=_PARALLEL_TASKS_CANCELLATION,
        )

        # stop stale_tasks_monitor
        if self._task_stale_tasks_monitor:
            await cancel_wait_task(
                self._task_stale_tasks_monitor,
                max_delay=_MAX_EXCLUSIVE_TASK_CANCEL_TIMEOUT,
            )

        # stop tasks_monitor
        if self._task_tasks_monitor:
            await cancel_wait_task(self._task_tasks_monitor)

        if self.locks_redis_client_sdk is not None:
            await self.locks_redis_client_sdk.shutdown()

        await self._tasks_data.shutdown()

    async def _stale_tasks_monitor(self) -> None:
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

        self._started_event_task_stale_tasks_monitor.set()

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
            with suppress(TaskNotFoundError):
                task_status = await self.get_task_status(
                    task_id, with_task_context=task_context, exclude_to_remove=False
                )
                with log_context(
                    _logger,
                    logging.WARNING,
                    f"Removing stale task '{task_id}' with status '{task_status.model_dump_json()}'",
                ):
                    await self.remove_task(
                        task_id, with_task_context=task_context, wait_for_removal=True
                    )

    async def _cancelled_tasks_removal(self) -> None:
        """
        Periodically checks which tasks are marked for removal and attempts to remove the
        task if it's handled by this process.
        """
        self._started_event_task_cancelled_tasks_removal.set()

        tasks_data = await self._tasks_data.list_tasks_data()
        await limited_gather(
            *(
                self._attempt_to_remove_local_task(x.task_id)
                for x in tasks_data
                if x.marked_for_removal is True
            ),
            limit=_PARALLEL_TASKS_CANCELLATION,
        )

    async def _tasks_monitor(self) -> None:  # noqa: C901
        """
        A task which monitors locally running tasks and updates their status
        in the Redis store when they are done.
        """
        self._started_event_task_tasks_monitor.set()
        task_id: TaskId

        for task_id in set(self._created_tasks.keys()):
            if task := self._created_tasks.get(task_id, None):
                is_done = task.done()
                if not is_done:
                    # task is still running, do not update
                    continue

                # write to redis only when done
                task_data = await self._tasks_data.get_task_data(task_id)
                if task_data is None or task_data.is_done:
                    # already done and updatet data in redis
                    continue

                result_field: ResultField | None = None
                # get task result
                try:
                    result_field = ResultField(str_result=dumps(task.result()))
                except asyncio.InvalidStateError:
                    # task was not completed try again next time and see if it is done
                    continue
                except asyncio.CancelledError:
                    result_field = ResultField(
                        str_error=dumps(TaskCancelledError(task_id=task_id))
                    )
                    # NOTE: if the task is itself cancelled it shall re-raise: see https://superfastpython.com/asyncio-cancellederror-consumed/
                    current_task = asyncio.current_task()
                    assert current_task is not None  # nosec
                    if current_task.cancelling() > 0:
                        # owner function is being cancelled -> propagate cancellation
                        raise
                except Exception as e:  # pylint:disable=broad-except
                    allowed_errors = TaskRegistry.get_allowed_errors(
                        task_data.registered_task_name
                    )
                    if type(e) not in allowed_errors:
                        _logger.exception(
                            **create_troubleshooting_log_kwargs(
                                (
                                    f"Execution of {task_id=} finished with unexpected error, "
                                    f"only the following {allowed_errors=} are permitted"
                                ),
                                error=e,
                                error_context={
                                    "task_id": task_id,
                                    "task_data": task_data,
                                    "namespace": self.lrt_namespace,
                                },
                            ),
                        )
                    try:
                        result_field = ResultField(str_error=dumps(e))
                    except (
                        Exception  # pylint:disable=broad-except
                    ) as serialization_error:
                        _logger.exception(
                            **create_troubleshooting_log_kwargs(
                                (
                                    f"Execution of {task_id=} finished with an error "
                                    f"which could not be serialized"
                                ),
                                error=serialization_error,
                                tip="Check the error above for more details",
                            ),
                        )
                        result_field = ResultField(
                            str_error=dumps(
                                TaskRaisedUnserializableError(
                                    task_id=task_id,
                                    exception=serialization_error,
                                    original_exception_str=f"{e}",
                                )
                            )
                        )

                # update and store in Redis
                updates = {"is_done": is_done, "result_field": task_data.result_field}
                if result_field is not None:
                    updates["result_field"] = result_field
                await self._tasks_data.update_task_data(task_id, updates=updates)

    async def list_tasks(self, with_task_context: TaskContext | None) -> list[TaskBase]:
        if not with_task_context:
            return [
                TaskBase(task_id=task.task_id)
                for task in (await self._tasks_data.list_tasks_data())
                if task.marked_for_removal is False
            ]

        return [
            TaskBase(task_id=task.task_id)
            for task in (await self._tasks_data.list_tasks_data())
            if task.task_context == with_task_context
            and task.marked_for_removal is False
        ]

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
        self,
        task_id: TaskId,
        with_task_context: TaskContext,
        *,
        exclude_to_remove: bool = True,
    ) -> TaskStatus:
        """
        returns: the status of the task, along with updates
        form the progress

        raises TaskNotFoundError if the task cannot be found
        """
        if exclude_to_remove and await self._tasks_data.is_marked_for_removal(task_id):
            raise TaskNotFoundError(task_id=task_id)

        task_data = await self._get_tracked_task(task_id, with_task_context)

        await self._tasks_data.update_task_data(
            task_id,
            updates={"last_status_check": datetime.datetime.now(tz=datetime.UTC)},
        )
        return TaskStatus.model_validate(
            {
                "task_progress": task_data.task_progress,
                "done": task_data.is_done,
                "started": task_data.started,
            }
        )

    async def get_allowed_errors(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> AllowedErrrors:
        """
        returns: the allowed errors for the task

        raises TaskNotFoundError if the task cannot be found
        """
        task_data = await self._get_tracked_task(task_id, with_task_context)
        return TaskRegistry.get_allowed_errors(task_data.registered_task_name)

    async def get_task_result(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> ResultField:
        """
        returns: the result of the task wrapped in ResultField

        raises TaskNotFoundError if the task cannot be found
        raises TaskNotCompletedError if the task is not completed
        """
        if await self._tasks_data.is_marked_for_removal(task_id):
            raise TaskNotFoundError(task_id=task_id)

        tracked_task = await self._get_tracked_task(task_id, with_task_context)

        if not tracked_task.is_done or tracked_task.result_field is None:
            raise TaskNotCompletedError(task_id=task_id)

        return tracked_task.result_field

    async def _attempt_to_remove_local_task(self, task_id: TaskId) -> None:
        """if task is running in the local process, try to remove it"""

        task_to_cancel = self._created_tasks.pop(task_id, None)
        if task_to_cancel is not None:
            _logger.debug("Removing asyncio task related to task_id='%s'", task_id)
            await cancel_wait_task(task_to_cancel)
            await self._tasks_data.delete_task_data(task_id)
        else:
            task_data = await self._tasks_data.get_task_data(task_id)
            if task_data.marked_for_removal_at is not None and datetime.datetime.now(  # type: ignore[union-attr]
                tz=datetime.UTC
            ) - task_data.marked_for_removal_at > datetime.timedelta(  # type: ignore[union-attr]
                seconds=_TASK_REMOVAL_MAX_WAIT
            ):
                _logger.debug(
                    "Force removing task_id='%s' from Redis after waiting for %s seconds",
                    task_id,
                    _TASK_REMOVAL_MAX_WAIT,
                )
                await self._tasks_data.delete_task_data(task_id)

    async def remove_task(
        self,
        task_id: TaskId,
        with_task_context: TaskContext,
        *,
        wait_for_removal: bool,
    ) -> None:
        """
        cancels and removes task
        raises TaskNotFoundError if the task cannot be found
        """
        if await self._tasks_data.is_marked_for_removal(task_id):
            raise TaskNotFoundError(task_id=task_id)

        tracked_task = await self._get_tracked_task(task_id, with_task_context)

        await self._tasks_data.mark_for_removal(tracked_task.task_id)

        if not wait_for_removal:
            return

        # wait for task to be removed since it might not have been running
        # in this process
        with suppress(TaskNotFoundError):
            async for attempt in AsyncRetrying(
                wait=wait_exponential(max=1),
                stop=stop_after_delay(_TASK_REMOVAL_MAX_WAIT),
                retry=retry_unless_exception_type(TaskNotFoundError),
            ):
                with attempt:
                    await self._get_tracked_task(
                        tracked_task.task_id, tracked_task.task_context
                    )

    def _get_task_id(self, task_name: str, *, is_unique: bool) -> TaskId:
        suffix = "unique" if is_unique else f"{uuid4()}"
        return f"{self.lrt_namespace}.{task_name}.{suffix}"

    async def _update_progress(
        self,
        task_id: TaskId,
        task_context: TaskContext,
        task_progress: TaskProgress,
    ) -> None:
        # NOTE: avoids errors while updating progress, since the task could have been
        # cancelled and it's data removed
        try:
            tracked_data = await self._get_tracked_task(task_id, task_context)
            tracked_data.task_progress = task_progress
            await self._tasks_data.update_task_data(
                task_id, updates={"task_progress": task_progress.model_dump()}
            )
        except TaskNotFoundError:
            _logger.debug(
                "Task '%s' not found while updating progress %s",
                task_id,
                task_progress,
            )

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
        registered_tasks = TaskRegistry.get_registered_tasks()
        if registered_task_name not in registered_tasks:
            raise TaskNotRegisteredError(
                task_name=registered_task_name, tasks=registered_tasks
            )

        task = TaskRegistry.get_task(registered_task_name)

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

        async def _task_with_progress(progress: TaskProgress, handler: TaskProtocol):
            # bind the task with progress 0 and 1
            await progress.update(message="starting", percent=0)
            try:
                return await handler(progress, **task_kwargs)
            finally:
                await progress.update(message="finished", percent=1)

        self._created_tasks[task_id] = asyncio.create_task(
            _task_with_progress(task_progress, task), name=task_name
        )

        tracked_task = TaskData(
            registered_task_name=registered_task_name,
            task_id=task_id,
            task_progress=task_progress,
            task_context=context_to_use,
            fire_and_forget=fire_and_forget,
        )
        await self._tasks_data.add_task_data(task_id, tracked_task)
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
