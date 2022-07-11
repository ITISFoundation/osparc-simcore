from typing import Any, Optional

from fastapi import APIRouter, Depends, status

from ._dependencies import get_task_manager
from ._errors import TaskNotCompletedError
from ._models import TaskId, TaskStatus
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
    task_manger: TaskManager = Depends(get_task_manager),
) -> TaskStatus:
    return task_manger.get_status(task_id=task_id)


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
    task_manger: TaskManager = Depends(get_task_manager),
) -> Optional[Any]:
    remove_task = True

    try:
        task_result = task_manger.get_result(task_id=task_id)
    except TaskNotCompletedError:
        remove_task = False
        raise
    finally:
        if remove_task:
            await task_manger.remove(task_id)

    return task_result


@router.delete(
    "/{task_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
async def cancel_and_delete_task(
    task_id: TaskId,
    task_manger: TaskManager = Depends(get_task_manager),
) -> bool:
    return await task_manger.remove(task_id)
