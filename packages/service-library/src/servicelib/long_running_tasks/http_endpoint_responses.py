from typing import Any

from .models import TaskGetWithoutHref, TaskId, TaskStatus
from .task import TaskContext, TasksManager, TrackedTask


def list_tasks(
    tasks_manager: TasksManager, task_context: TaskContext | None
) -> list[TaskGetWithoutHref]:
    tracked_tasks: list[TrackedTask] = tasks_manager.list_tasks(
        with_task_context=task_context
    )
    return [
        TaskGetWithoutHref(task_id=t.task_id, task_name=t.task_name)
        for t in tracked_tasks
    ]


def get_task_status(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> TaskStatus:
    return tasks_manager.get_task_status(
        task_id=task_id, with_task_context=task_context
    )


async def get_task_result(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> Any:
    try:
        return tasks_manager.get_task_result(
            task_id=task_id, with_task_context=task_context
        )
    finally:
        # the task is always removed even if an error occurs
        await tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )


async def remove_task(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> None:
    await tasks_manager.remove_task(task_id, with_task_context=task_context)
