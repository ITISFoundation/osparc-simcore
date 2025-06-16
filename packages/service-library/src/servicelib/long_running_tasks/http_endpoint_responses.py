from typing import Any

from .errors import TaskNotCompletedError, TaskNotFoundError
from .models import TaskBase, TaskId, TaskStatus
from .task import TaskContext, TasksManager, TrackedTask


def list_tasks(
    tasks_manager: TasksManager, task_context: TaskContext | None
) -> list[TaskBase]:
    tracked_tasks: list[TrackedTask] = tasks_manager.list_tasks(
        with_task_context=task_context
    )
    return [TaskBase(task_id=t.task_id, task_name=t.task_name) for t in tracked_tasks]


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
        task_result = tasks_manager.get_task_result(
            task_id, with_task_context=task_context
        )
        await tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )
        return task_result
    except (TaskNotFoundError, TaskNotCompletedError):
        raise
    except Exception:
        # the task shall be removed in this case
        await tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )
        raise


async def remove_task(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> None:
    await tasks_manager.remove_task(task_id, with_task_context=task_context)
