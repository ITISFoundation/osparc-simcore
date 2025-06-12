from typing import Any

from .models import TaskBase, TaskId, TaskStatus
from .task import TaskContext, TasksManager, TrackedTask


def list_tasks(
    tasks_manager: TasksManager, task_context: TaskContext | None
) -> list[TaskBase]:
    tracked_tasks: list[TrackedTask] = tasks_manager.list_tasks(
        with_task_context=task_context
    )
    return [TaskBase(task_id=t.task_id) for t in tracked_tasks]


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


# TODO reroute start via this with registration of hanlders

# TODO: to support this we need handler registration capability in order to figure out if they can be started
# this should be done via the final TasksManager
# - also

# TODO: this should be used to start everywhere not the client's start_task actually,
# this way we completly isolate everything and are allowed to call it form everywhere
# async def start_task(
#     tasks_manager: TasksManager,
#     task: TaskContext | None,
#     task_context: TaskContext | None = None,
#     **task_kwargs: Any,
# ) -> TaskId:
#     return tasks_manager.start_task(
#         task=task, task_context=task_context, **task_kwargs
#     )
