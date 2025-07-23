import logging
from typing import Any

from common_library.error_codes import create_error_code
from servicelib.logging_errors import create_troubleshootting_log_kwargs

from .errors import TaskNotCompletedError, TaskNotFoundError
from .models import TaskBase, TaskContext, TaskId, TaskStatus
from .task import RegisteredTaskName, TasksManager

_logger = logging.getLogger(__name__)


async def start_task(
    tasks_manager: TasksManager,
    registered_task_name: RegisteredTaskName,
    *,
    unique: bool = False,
    task_context: TaskContext | None = None,
    task_name: str | None = None,
    fire_and_forget: bool = False,
    **task_kwargs: Any,
) -> TaskId:
    """
    Creates a background task from an async function.

    An asyncio task will be created out of it by injecting a `TaskProgress` as the first
    positional argument and adding all `handler_kwargs` as named parameters.

    NOTE: the progress is automatically bounded between 0 and 1
    NOTE: the `task` name must be unique in the module, otherwise when using
        the unique parameter is True, it will not be able to distinguish between
        them.

    Args:
        tasks_manager (TasksManager): the tasks manager
        task (TaskProtocol): the tasks to be run in the background
        unique (bool, optional): If True, then only one such named task may be run. Defaults to False.
        task_context (Optional[TaskContext], optional): a task context storage can be retrieved during the task lifetime. Defaults to None.
        task_name (Optional[str], optional): optional task name. Defaults to None.
        fire_and_forget: if True, then the task will not be cancelled if the status is never called

    Raises:
        TaskAlreadyRunningError: if unique is True, will raise if more than 1 such named task is started

    Returns:
        TaskId: the task unique identifier
    """
    return await tasks_manager.start_task(
        registered_task_name,
        unique=unique,
        task_context=task_context,
        task_name=task_name,
        fire_and_forget=fire_and_forget,
        **task_kwargs,
    )


async def list_tasks(
    tasks_manager: TasksManager, task_context: TaskContext | None
) -> list[TaskBase]:
    return await tasks_manager.list_tasks(with_task_context=task_context)


async def get_task_status(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> TaskStatus:
    """returns the status of a task"""
    return await tasks_manager.get_task_status(
        task_id=task_id, with_task_context=task_context
    )


async def get_task_result(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> Any:
    try:
        task_result = await tasks_manager.get_task_result(
            task_id, with_task_context=task_context
        )
        await tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )
        return task_result
    except (TaskNotFoundError, TaskNotCompletedError):
        raise
    except Exception as exc:
        _logger.exception(
            **create_troubleshootting_log_kwargs(
                user_error_msg=f"{task_id=} raised an exception while getting its result",
                error=exc,
                error_code=create_error_code(exc),
                error_context={"task_context": task_context, "task_id": task_id},
            ),
        )
        # the task shall be removed in this case
        await tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )
        raise


async def remove_task(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> None:
    """removes / cancels a task"""
    await tasks_manager.remove_task(task_id, with_task_context=task_context)


async def cancel_task(
    tasks_manager: TasksManager, task_context: TaskContext | None, task_id: TaskId
) -> None:
    """cancels a task"""
    await tasks_manager.cancel_task(task_id, with_task_context=task_context)
