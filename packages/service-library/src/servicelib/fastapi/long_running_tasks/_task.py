import asyncio
import inspect
import logging
import traceback
from asyncio import CancelledError, Task
from collections import deque
from contextlib import suppress
from datetime import datetime
from typing import Awaitable, Callable
from uuid import uuid4

from pydantic import PositiveFloat

from ._errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskExceptionError,
    TaskNotCompletedError,
    TaskNotFoundError,
)
from ._models import TaskId, TaskName, TaskProgress, TaskResult, TaskStatus, TrackedTask

logger = logging.getLogger(__name__)


async def _await_task(task: Task):
    await task


class TaskManager:
    def __init__(
        self,
        stale_task_check_interval_s: PositiveFloat,
        stale_task_detect_timeout_s: PositiveFloat,
    ) -> None:
        self.tasks: dict[TaskName, dict[TaskId, TrackedTask]] = {}

        self._cancel_task_timeout_s: PositiveFloat = 1.0

        self.stale_task_check_interval_s = stale_task_check_interval_s
        self.stale_task_detect_timeout_s = stale_task_detect_timeout_s
        self._stale_tasks_monitor_task: Task = asyncio.create_task(
            self._stale_tasks_monitor_worker()
        )

    async def _stale_tasks_monitor_worker(self) -> None:
        """
        A task is considered stale, if the task status is not queried
        in the last `stale_task_detect_timeout_s`.

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

        def _mark_task_to_remove_if_required(
            tasks_to_remove: list[TaskId], tracked_task: TrackedTask, utc_now: datetime
        ) -> None:

            if tracked_task.last_status_check is None:
                # the task just added or never received a poll request
                elapsed_from_start = (utc_now - tracked_task.started).seconds
                if elapsed_from_start > self.stale_task_detect_timeout_s:
                    tasks_to_remove.append(task_id)
            else:
                # the task status was already queried by the client
                elapsed_from_last_poll = (
                    utc_now - tracked_task.last_status_check
                ).seconds
                if elapsed_from_last_poll > self.stale_task_detect_timeout_s:
                    tasks_to_remove.append(task_id)

        while True:
            await asyncio.sleep(self.stale_task_check_interval_s)

            utc_now = datetime.utcnow()

            tasks_to_remove: list[TaskId] = []
            for tasks in self.tasks.values():
                for task_id, tracked_task in tasks.items():
                    _mark_task_to_remove_if_required(
                        tasks_to_remove, tracked_task, utc_now
                    )

            # finally remove tasks and warn
            for task_id in tasks_to_remove:
                # NOTE: task can be in the following cases:
                # - still ongoing
                # - finished with a result
                # - finished with errors
                # we just print the status from where one can infer the above
                logger.warning(
                    "Removing stale task '%s' with status '%s'",
                    task_id,
                    self.get_status(task_id).json(),
                )
                await self.remove(task_id, reraise_errors=False)

    @staticmethod
    def get_task_id(task_name: TaskName) -> str:
        return f"{task_name}.{uuid4()}"

    def is_task_name_running(self, task_name: TaskName) -> bool:
        """returns True if a task named `task_name` is running"""
        if task_name not in self.tasks:
            return False

        managed_tasks_ids = list(self.tasks[task_name].keys())
        return len(managed_tasks_ids) > 0

    def add(
        self, task_name: TaskName, task: Task, task_progress: TaskProgress
    ) -> TrackedTask:
        task_id = self.get_task_id(task_name)

        if task_name not in self.tasks:
            self.tasks[task_name] = {}

        tracked_task = TrackedTask.parse_obj(
            dict(
                task_id=task_id,
                task=task,
                task_name=task_name,
                task_progress=task_progress,
            )
        )
        self.tasks[task_name][task_id] = tracked_task

        return tracked_task

    def _get_tracked_task(self, task_id: TaskId) -> TrackedTask:
        for tasks in self.tasks.values():
            if task_id in tasks:
                tracked_task = tasks[task_id]
                return tracked_task

        raise TaskNotFoundError(task_id=task_id)

    def get_status(self, task_id: TaskId) -> TaskStatus:
        """
        returns: the status of the task, along with updates
        form the progress

        raises TaskNotFoundError if the task cannot be found
        """
        tracked_task: TrackedTask = self._get_tracked_task(task_id)
        tracked_task.last_status_check = datetime.utcnow()

        task = tracked_task.task
        done = task.done()

        return TaskStatus.parse_obj(
            dict(
                task_progress=tracked_task.task_progress,
                done=done,
                started=tracked_task.started,
            )
        )

    def get_result(self, task_id: TaskId) -> TaskResult:
        """
        returns: the result of the task

        raises TaskNotFoundError if the task cannot be found
        """
        tracked_task = self._get_tracked_task(task_id)

        if not tracked_task.task.done():
            raise TaskNotCompletedError(task_id=task_id)

        try:
            exception = tracked_task.task.exception()
            if exception is not None:
                formatted_traceback = "\n".join(
                    traceback.format_tb(exception.__traceback__)
                )
                error = TaskExceptionError(
                    task_id=task_id, exception=exception, traceback=formatted_traceback
                )
                return TaskResult(result=None, error=f"{error}")
        except CancelledError:
            error = TaskCancelledError(task_id=task_id)
            return TaskResult(result=None, error=f"{error}")

        return TaskResult(result=tracked_task.task.result(), error=None)

    async def cancel_task(self, task_id: TaskId) -> None:
        """
        cancels the task

        raises TaskNotFoundError if the task cannot be found
        """
        tracked_task = self._get_tracked_task(task_id)
        await self._cancel_tracked_task(tracked_task.task, task_id, reraise_errors=True)

    async def _cancel_asyncio_task(
        self, task: Task, reference: str, *, reraise_errors: bool
    ) -> None:
        task.cancel()
        with suppress(CancelledError):
            try:
                try:
                    await asyncio.wait_for(
                        _await_task(task), timeout=self._cancel_task_timeout_s
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timed out while awaiting for cancellation of '%s'", reference
                    )
            except Exception:  # pylint:disable=broad-except
                if reraise_errors:
                    raise

    async def _cancel_tracked_task(
        self, task: Task, task_id: TaskId, *, reraise_errors: bool
    ) -> None:
        try:
            await self._cancel_asyncio_task(
                task, task_id, reraise_errors=reraise_errors
            )
        except Exception as e:  # pylint:disable=broad-except
            formatted_traceback = "\n".join(traceback.format_tb(e.__traceback__))
            raise TaskExceptionError(
                task_id=task_id, exception=e, traceback=formatted_traceback
            ) from e

    async def remove(self, task_id: TaskId, *, reraise_errors: bool = True) -> bool:
        """cancels and removes task"""
        for tasks in self.tasks.values():
            if task_id in tasks:
                try:
                    await self._cancel_tracked_task(
                        tasks[task_id].task, task_id, reraise_errors=reraise_errors
                    )
                finally:
                    del tasks[task_id]
                return True
        return False

    async def close(self) -> None:
        """
        cancels all pending tasks and removes them before closing
        """
        task_ids_to_remove: deque[TaskId] = deque()

        for tasks_dict in self.tasks.values():
            for tracked_task in tasks_dict.values():
                task_ids_to_remove.append(tracked_task.task_id)

        for task_id in task_ids_to_remove:
            # when closing we do not care about pending errors
            await self.remove(task_id, reraise_errors=False)

        await self._cancel_asyncio_task(
            self._stale_tasks_monitor_task, "stale_monitor", reraise_errors=False
        )


def start_task(
    task_manager: TaskManager,
    handler: Callable[..., Awaitable],
    *,
    unique: bool = False,
    **kwargs,
) -> TaskId:
    """
    Creates a task from a given callable to an async function.
    A task will be created out of it by injecting a `TaskProgress` as the first
    positional argument and adding all `kwargs` as named parameters.

    NOTE: the first progress update will be (message='', percent=0.0)
    NOTE: the `handler` name must be unique in the module, otherwise when using
        the unique parameter is True, it will not be able to distinguish between
        the them.
    """

    # NOTE: Composing the task_name out of the handler's module and it's name
    # to keep the urls shorter and more meaningful.
    handler_module = inspect.getmodule(handler)
    handler_module_name = handler_module.__name__ if handler_module else ""
    task_name = f"{handler_module_name}.{handler.__name__}"

    # only one unique task can be running
    if unique and task_manager.is_task_name_running(task_name):
        managed_tasks_ids = list(task_manager.tasks[task_name].keys())
        assert len(managed_tasks_ids) == 1  # nosec
        managed_task = task_manager.tasks[task_name][managed_tasks_ids[0]]
        raise TaskAlreadyRunningError(task_name=task_name, managed_task=managed_task)

    task_progress = TaskProgress.create()
    awaitable = handler(task_progress, **kwargs)
    task = asyncio.create_task(awaitable)

    tracked_task = task_manager.add(
        task_name=task_name, task=task, task_progress=task_progress
    )
    return tracked_task.task_id
