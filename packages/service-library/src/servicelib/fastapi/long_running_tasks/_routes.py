from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from ...long_running_tasks import lrt_api
from ...long_running_tasks.models import TaskGet, TaskId, TaskResult, TaskStatus
from ...long_running_tasks.utils import decode_error_types
from ..requests_decorators import cancel_on_disconnect
from ._dependencies import get_long_running_manager
from ._manager import FastAPILongRunningManager

router = APIRouter(prefix="/task")


@router.get("", response_model=list[TaskGet])
@cancel_on_disconnect
async def list_tasks(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> list[TaskGet]:
    assert request  # nosec
    return [
        TaskGet(
            task_id=t.task_id,
            status_href=str(request.url_for("get_task_status", task_id=t.task_id)),
            result_href=str(request.url_for("get_task_result", task_id=t.task_id)),
            abort_href=str(request.url_for("remove_task", task_id=t.task_id)),
        )
        for t in await lrt_api.list_tasks(
            long_running_manager.rpc_client, long_running_manager, task_context={}
        )
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
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskStatus:
    assert request  # nosec
    return await lrt_api.get_task_status(
        long_running_manager.rpc_client,
        long_running_manager,
        task_context={},
        task_id=task_id,
    )


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
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
    allowed_errors: Annotated[
        str,
        Query(
            description="list of json encoded tuples of allowed errors",
            example='["tests.fastapi.long_running_tasks.test_long_running_tasks", "_TestingError"]',
        ),
    ] = "",
) -> TaskResult | Any:
    assert request  # nosec
    return await lrt_api.get_task_result(
        long_running_manager.rpc_client,
        long_running_manager,
        task_context={},
        task_id=task_id,
        allowed_errors=decode_error_types(allowed_errors),
    )


@router.delete(
    "/{task_id}",
    summary="Cancels and removes a task",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Task does not exist"},
    },
)
@cancel_on_disconnect
async def remove_task(
    request: Request,
    task_id: TaskId,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> None:
    assert request  # nosec
    await lrt_api.remove_task(
        long_running_manager.rpc_client,
        long_running_manager,
        task_context={},
        task_id=task_id,
        wait_for_removal=True,  # only used by internal services, they will wait as before
    )
