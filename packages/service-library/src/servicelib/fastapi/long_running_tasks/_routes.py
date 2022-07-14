from typing import Any, Optional

from fastapi import APIRouter, Depends, status

from ._dependencies import get_task_manager
from ._errors import TaskNotCompletedError
from ._models import TaskId, TaskResult, TaskStatus
from ._task import TaskManager

router = APIRouter(prefix="/task")


@router.get(
    "/{task_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
async def get_task_status(
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskStatus:
    return task_manager.get_status(task_id=task_id)


@router.get(
    "/{task_id}/result",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Task cancelled or finished with exception"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
async def get_task_result(
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskResult:
    remove_task = True

    try:
        task_result = task_manager.get_result(task_id=task_id)
    except TaskNotCompletedError:
        remove_task = False
        raise
    finally:
        if remove_task:
            await task_manager.remove(task_id, reraise_errors=False)

    return task_result


@router.delete(
    "/{task_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
async def cancel_and_delete_task(
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> bool:
    return await task_manager.remove(task_id)
