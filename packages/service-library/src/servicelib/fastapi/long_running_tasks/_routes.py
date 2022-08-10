from fastapi import APIRouter, Depends, Request, status

from ...long_running_tasks._models import TaskId, TaskResult, TaskStatus
from ...long_running_tasks._task import TaskManager
from ..requests_decorators import cancel_on_disconnect
from ._dependencies import get_task_manager

router = APIRouter(prefix="/task")


@router.get(
    "/{task_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
@cancel_on_disconnect
async def get_task_status(
    request: Request,
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskStatus:
    assert request  # nosec
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
@cancel_on_disconnect
async def get_task_result(
    request: Request,
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskResult:
    assert request  # nosec

    task_result = task_manager.get_result(task_id=task_id)
    await task_manager.remove(task_id, reraise_errors=False)

    return task_result


@router.delete(
    "/{task_id}",
    summary="Cancel and deletes a task",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
@cancel_on_disconnect
async def cancel_and_delete_task(
    request: Request,
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> None:
    assert request  # nosec
    await task_manager.remove(task_id)
