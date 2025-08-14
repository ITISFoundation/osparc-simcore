import logging
import traceback
from typing import Any

from ...rabbitmq import RPCRouter
from .._serialization import object_to_string
from ..base_long_running_manager import BaseLongRunningManager
from ..errors import BaseLongRunningError, TaskNotCompletedError, TaskNotFoundError
from ..models import TaskBase, TaskContext, TaskId, TaskStatus
from ..task import RegisteredTaskName
from ._models import RPCErrorResponse

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


async def _get_transferarble_task_result(
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
    except Exception:
        # the task shall be removed in this case
        await long_running_manager.tasks_manager.remove_task(
            task_id, with_task_context=task_context, reraise_errors=False
        )
        raise


@router.expose(reraise_if_error_type=(BaseLongRunningError, Exception))
async def get_task_result(
    long_running_manager: BaseLongRunningManager,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> RPCErrorResponse | str:
    try:
        return object_to_string(
            await _get_transferarble_task_result(
                long_running_manager, task_context=task_context, task_id=task_id
            )
        )
    except Exception as exc:  # pylint:disable=broad-exception-caught
        return RPCErrorResponse(
            str_traceback="".join(traceback.format_tb(exc.__traceback__)),
            error_object=object_to_string(exc),
        )


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
