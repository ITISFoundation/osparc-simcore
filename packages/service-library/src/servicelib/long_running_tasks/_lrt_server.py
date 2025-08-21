import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from ..logging_errors import create_troubleshootting_log_kwargs
from ..rabbitmq import RPCRouter
from ._serialization import string_to_object
from .errors import BaseLongRunningError, TaskNotFoundError
from .models import (
    ErrorResponse,
    RegisteredTaskName,
    TaskBase,
    TaskContext,
    TaskId,
    TaskStatus,
)

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .base_long_running_manager import BaseLongRunningManager


router = RPCRouter()


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def start_task(
    long_running_manager: "BaseLongRunningManager",
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
    long_running_manager: "BaseLongRunningManager", *, task_context: TaskContext
) -> list[TaskBase]:
    return await long_running_manager.tasks_manager.list_tasks(
        with_task_context=task_context
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def get_task_status(
    long_running_manager: "BaseLongRunningManager",
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> TaskStatus:
    return await long_running_manager.tasks_manager.get_task_status(
        task_id=task_id, with_task_context=task_context
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def get_task_result(
    long_running_manager: "BaseLongRunningManager",
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> ErrorResponse | str:
    try:
        result_field = await long_running_manager.tasks_manager.get_task_result(
            task_id, with_task_context=task_context
        )
        if result_field.error_response is not None:
            task_raised_error_traceback = result_field.error_response.str_traceback
            task_raised_error = string_to_object(
                result_field.error_response.str_error_object
            )
            _logger.info(
                **create_troubleshootting_log_kwargs(
                    f"Execution of {task_id=} finished with error:\n{task_raised_error_traceback}",
                    error=task_raised_error,
                    error_context={
                        "task_id": task_id,
                        "task_context": task_context,
                        "namespace": long_running_manager.lrt_namespace,
                    },
                    tip="This exception is logged for debugging purposes, the client side will handle it",
                )
            )
            allowed_errors = (
                await long_running_manager.tasks_manager.get_allowed_errors(
                    task_id, with_task_context=task_context
                )
            )
            if type(task_raised_error) in allowed_errors:
                return result_field.error_response

            raise task_raised_error

        if result_field.str_result is not None:
            return result_field.str_result

        msg = f"Please check {result_field=}, both fields should never be None"
        raise ValueError(msg)
    finally:
        # Ensure the task is removed regardless of the result
        with suppress(TaskNotFoundError):
            await long_running_manager.tasks_manager.remove_task(
                task_id,
                with_task_context=task_context,
                wait_for_removal=True,
            )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def remove_task(
    long_running_manager: "BaseLongRunningManager",
    *,
    task_context: TaskContext,
    task_id: TaskId,
    wait_for_removal: bool,
) -> None:
    await long_running_manager.tasks_manager.remove_task(
        task_id,
        with_task_context=task_context,
        wait_for_removal=wait_for_removal,
    )
