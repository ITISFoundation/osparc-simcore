from fastapi import APIRouter, Depends, Request, status

from ..requests_decorators import cancel_on_disconnect
from ._dependencies import get_task_manager
from ._errors import TaskNotCompletedError
from ._models import CancelResult, TaskId, TaskResult, TaskStatus
from ._task import TaskManager

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
@cancel_on_disconnect
async def cancel_and_delete_task(
    request: Request,
    task_id: TaskId,
    task_manager: TaskManager = Depends(get_task_manager),
) -> CancelResult:
    assert request  # nosec
    return CancelResult(task_removed=await task_manager.remove(task_id))
