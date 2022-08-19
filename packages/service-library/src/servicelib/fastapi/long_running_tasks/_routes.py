from fastapi import APIRouter, Depends, Request, status

from ...long_running_tasks._errors import TaskNotCompletedError, TaskNotFoundError
from ...long_running_tasks._models import TaskId, TaskResult, TaskStatus
from ...long_running_tasks._task import TasksManager
from ..requests_decorators import cancel_on_disconnect
from ._dependencies import get_tasks_manager

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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
) -> TaskStatus:
    assert request  # nosec
    return tasks_manager.get_task_status(task_id=task_id)


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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
) -> TaskResult:
    assert request  # nosec
    # TODO: refactor this to use same as in https://github.com/ITISFoundation/osparc-simcore/issues/3265
    try:
        task_result = tasks_manager.get_task_result_old(task_id=task_id)
        await tasks_manager.remove_task(task_id, reraise_errors=False)
        return task_result
    except (TaskNotFoundError, TaskNotCompletedError):
        raise
    except Exception:
        # the task shall be removed in this case
        await tasks_manager.remove_task(task_id, reraise_errors=False)
        raise


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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
) -> None:
    assert request  # nosec
    await tasks_manager.remove_task(task_id)
