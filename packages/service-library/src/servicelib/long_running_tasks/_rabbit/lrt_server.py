import logging
from typing import Any

from common_library.error_codes import create_error_code

from ...logging_errors import create_troubleshootting_log_kwargs
from ...rabbitmq import RPCRouter
from ..base_long_running_manager import BaseLongRunningManager
from ..errors import BaseLongRunningError, TaskNotCompletedError, TaskNotFoundError
from ..models import TaskBase, TaskContext, TaskId, TaskStatus
from ..task import RegisteredTaskName

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def start_task(
    long_running_manager: BaseLongRunningManager,
    *,
    registered_task_name: RegisteredTaskName,
    unique: bool = False,
    task_context: TaskContext | None = None,
    task_name: str | None = None,
    fire_and_forget: bool = False,
    **task_kwargs: Any,
) -> TaskId:
    return await long_running_manager.tasks_manager.start_task(
        registered_task_name,
        unique=unique,
        task_context=task_context,
        task_name=task_name,
        fire_and_forget=fire_and_forget,
        **task_kwargs,
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def list_tasks(
    long_running_manager: BaseLongRunningManager, *, task_context: TaskContext
) -> list[TaskBase]:
    return await long_running_manager.tasks_manager.list_tasks(
        with_task_context=task_context
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def get_task_status(
    long_running_manager: BaseLongRunningManager,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> TaskStatus:
    return await long_running_manager.tasks_manager.get_task_status(
        task_id=task_id, with_task_context=task_context
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError, Exception))
async def get_task_result(
    long_running_manager: BaseLongRunningManager,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> Any:
    try:
        task_result = await long_running_manager.tasks_manager.get_task_result(
            task_id, with_task_context=task_context
        )
        await long_running_manager.tasks_manager.remove_task(
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
        await long_running_manager.tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )
        raise


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def remove_task(
    long_running_manager: BaseLongRunningManager,
    *,
    task_context: TaskContext,
    task_id: TaskId,
    reraise_errors: bool,
) -> None:
    await long_running_manager.tasks_manager.remove_task(
        task_id, with_task_context=task_context, reraise_errors=reraise_errors
    )
