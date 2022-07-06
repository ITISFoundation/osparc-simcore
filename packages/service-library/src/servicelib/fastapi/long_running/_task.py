from contextlib import suppress
from pydantic import BaseModel, Field
import logging
from typing import Any, Awaitable, Callable, Optional
from collections import deque
from ._models import TaskName, ProgressHandler, TrackedTask, TaskId, TaskStatus
from uuid import uuid4
from asyncio import Task, CancelledError
import asyncio
from ._errors import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskNotCompletedError,
    TaskCancelledError,
    TaskExceptionError,
)

logger = logging.getLogger(__name__)


class TaskManager(BaseModel):
    tasks: dict[TaskName, dict[TaskId, TrackedTask]] = Field(default_factory=dict)

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
        self, task_name: TaskName, task: Task, progress_handler: ProgressHandler
    ) -> TrackedTask:
        """keep track of a task, if unique is True, only one of these can be running at a time"""

        task_id = self.get_task_id(task_name)

        tracked_task = TrackedTask.parse_obj(
            dict(
                task_id=task_id,
                task=task,
                task_name=task_name,
                progress_handler=progress_handler,
            )
        )

        if task_name not in self.tasks:
            self.tasks[task_name] = {}
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
        tracked_task = self._get_tracked_task(task_id)
        task = tracked_task.task
        done = task.done()
        successful = task.done() and not task.cancelled()

        return TaskStatus.parse_obj(
            dict(
                progress=tracked_task.progress_handler,
                done=done,
                successful=successful,
                started=tracked_task.started,
            )
        )

    def get_result(self, task_id: TaskId) -> Optional[Any]:
        """
        returns: the result of the task

        raises TaskNotFoundError if the task cannot be found
        raises TaskExceptionError if task finished with an error
        raises TaskCancelledError if task was cancelled before completion
        """
        tracked_task = self._get_tracked_task(task_id)

        if not tracked_task.task.done():
            raise TaskNotCompletedError(task_id=task_id)

        try:
            exception = tracked_task.task.exception()
            if exception is not None:
                raise TaskExceptionError(task_id=task_id, exception=exception)
        except CancelledError as e:
            raise TaskCancelledError(task_id=task_id) from e

        return tracked_task.task.result()

    async def cancel_task(self, task_id: TaskId) -> None:
        """
        cancels the task

        raises TaskNotFoundError if the task cannot be found
        """
        tracked_task = self._get_tracked_task(task_id)
        await self._cancel_task(tracked_task.task, task_id, reraise_errors=True)

    @staticmethod
    async def _cancel_task(
        task: Task, task_id: TaskId, *, reraise_errors: bool
    ) -> None:
        task.cancel()
        with suppress(CancelledError):
            # TODO: also this should have a timeout when canceling since
            # these tasks can contain whatever locks
            try:
                await task
            except Exception as e:  # pylint:disable=broad-except
                if reraise_errors:
                    raise TaskExceptionError(task_id=task_id, exception=e) from e

    async def remove(self, task_id: TaskId, *, reraise_errors: bool = True) -> None:
        """cancels and removes task"""
        for tasks in self.tasks.values():
            if task_id in tasks:
                try:
                    await self._cancel_task(
                        tasks[task_id].task, task_id, reraise_errors=reraise_errors
                    )
                finally:
                    del tasks[task_id]

    async def close(self) -> None:
        # cancel all pending tasks and remove when closing
        task_ids_to_remove: deque[TaskId] = deque()

        for tasks_dict in self.tasks.values():
            for tracked_task in tasks_dict.values():
                task_ids_to_remove.append(tracked_task.task_id)

        for task_id in task_ids_to_remove:
            # when closing we do not care about pending errors
            await self.remove(task_id, reraise_errors=False)


def start_task(
    task_manager: TaskManager,
    handler: Callable[..., Awaitable],
    *,
    unique: bool = False,
    **kwargs,
) -> TaskId:
    task_name = handler.__qualname__

    # only one unique task can be running
    if unique and task_manager.is_task_name_running(task_name):
        managed_tasks_ids = list(task_manager.tasks[task_name].keys())
        assert len(managed_tasks_ids) == 1  # nosec
        managed_task = task_manager.tasks[task_name][managed_tasks_ids[0]]
        raise TaskAlreadyRunningError(task_name=task_name, managed_task=managed_task)

    progress = ProgressHandler.create()
    # NOTE: starlette's BackgroundTask is just awaited at the end
    # of a request after the response is sent.
    # It blocks the server until the request is complete.
    # Below is not what we want
    # background_tasks.add_task(_handle_task, background_task)
    awaitable = handler(ProgressHandler.create(), **kwargs)
    task = asyncio.create_task(awaitable)

    tracked_task = task_manager.add(
        task_name=task_name, task=task, progress_handler=progress
    )
    return tracked_task.task_id
