from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from ...long_running_tasks._errors import TaskNotCompletedError, TaskNotFoundError
from ...long_running_tasks._models import TaskGet, TaskId, TaskResult, TaskStatus
from ...long_running_tasks._task import TasksManager
from ..requests_decorators import cancel_on_disconnect
from ._dependencies import get_tasks_manager

router = APIRouter(prefix="/task")


@router.get("", response_model=list[TaskGet])
@cancel_on_disconnect
async def list_tasks(
    request: Request, tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)]
) -> list[TaskGet]:
    assert request  # nosec
    return [
        TaskGet(
            task_id=t.task_id,
            task_name=t.task_name,
            status_href="",
            result_href="",
            abort_href="",
        )
        for t in tasks_manager.list_tasks(with_task_context=None)
    ]


@router.get(
    "/{task_id}",
    response_model=TaskStatus,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
@cancel_on_disconnect
async def get_task_status(
    request: Request,
    task_id: TaskId,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
) -> TaskStatus:
    assert request  # nosec
    return tasks_manager.get_task_status(task_id=task_id, with_task_context=None)


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
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    *,
    return_exception: Annotated[bool, Query()] = False,
) -> TaskResult | Any:
    assert request  # nosec
    # TODO: refactor this to use same as in https://github.com/ITISFoundation/osparc-simcore/issues/3265
    try:
        if return_exception:
            task_result = tasks_manager.get_task_result(task_id, with_task_context=None)
        else:
            task_result = tasks_manager.get_task_result_old(task_id=task_id)
        await tasks_manager.remove_task(
            task_id, with_task_context=None, reraise_errors=False
        )
        return task_result
    except (TaskNotFoundError, TaskNotCompletedError):
        raise
    except Exception:
        # the task shall be removed in this case
        await tasks_manager.remove_task(
            task_id, with_task_context=None, reraise_errors=False
        )
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
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
) -> None:
    assert request  # nosec
    await tasks_manager.remove_task(task_id, with_task_context=None)
