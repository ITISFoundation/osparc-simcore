import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from ..rabbitmq import RPCRouter
from .errors import BaseLongRunningError, RPCTransferrableTaskError, TaskNotFoundError
from .models import (
    RegisteredTaskName,
    TaskBase,
    TaskContext,
    TaskId,
    TaskStatus,
)

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .manager import LongRunningManager


router = RPCRouter()


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def start_task(
    long_running_manager: "LongRunningManager",
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
    long_running_manager: "LongRunningManager", *, task_context: TaskContext
) -> list[TaskBase]:
    return await long_running_manager.tasks_manager.list_tasks(
        with_task_context=task_context
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def get_task_status(
    long_running_manager: "LongRunningManager",
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> TaskStatus:
    return await long_running_manager.tasks_manager.get_task_status(
        task_id=task_id, with_task_context=task_context
    )


@router.expose(reraise_if_error_type=(BaseLongRunningError, RPCTransferrableTaskError))
async def get_task_result(
    long_running_manager: "LongRunningManager",
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> str:
    try:
        result_field = await long_running_manager.tasks_manager.get_task_result(
            task_id, with_task_context=task_context
        )
        if result_field.str_error is not None:
            raise RPCTransferrableTaskError(result_field.str_error)

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
                wait_for_removal=False,
            )


@router.expose(reraise_if_error_type=(BaseLongRunningError,))
async def remove_task(
    long_running_manager: "LongRunningManager",
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> None:
    await long_running_manager.tasks_manager.remove_task(
        task_id, with_task_context=task_context, wait_for_removal=False
    )
