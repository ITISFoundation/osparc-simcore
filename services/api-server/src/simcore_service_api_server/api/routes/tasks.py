import logging
from typing import Annotated, Any

from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobId,
)
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.celery.models import TaskFilter, TaskUUID
from servicelib.fastapi.dependencies import get_app

from ...models.schemas.base import ApiServerEnvelope
from ...models.schemas.errors import ErrorGet
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.celery import ASYNC_JOB_CLIENT_NAME, get_task_manager_from_app
from ._constants import (
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

router = APIRouter()
_logger = logging.getLogger(__name__)


def _get_task_filter(user_id: UserID, product_name: ProductName) -> TaskFilter:
    job_filter = AsyncJobFilter(
        user_id=user_id, product_name=product_name, client_name=ASYNC_JOB_CLIENT_NAME
    )
    return TaskFilter.model_validate(job_filter.model_dump())


_DEFAULT_TASK_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal server error",
        "model": ErrorGet,
    },
}


@router.get(
    "",
    response_model=ApiServerEnvelope[list[TaskGet]],
    responses=_DEFAULT_TASK_STATUS_CODES,
    description=create_route_description(
        base="List all tasks",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10-rc1"),
        ],
    ),
    include_in_schema=True,
)
async def list_tasks(
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):

    task_manager = get_task_manager_from_app(app)

    try:
        tasks = await task_manager.list_tasks(
            task_filter=_get_task_filter(user_id, product_name),
        )
    except CeleryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encountered issue when listing tasks",
        ) from exc

    app_router = app.router
    data = [
        TaskGet(
            task_id=f"{task.uuid}",
            task_name=task.metadata.name,
            status_href=app_router.url_path_for(
                "get_task_status", task_id=f"{task.uuid}"
            ),
            abort_href=app_router.url_path_for("cancel_task", task_id=f"{task.uuid}"),
            result_href=app_router.url_path_for(
                "get_task_result", task_id=f"{task.uuid}"
            ),
        )
        for task in tasks
    ]
    return ApiServerEnvelope(data=data)


@router.get(
    "/{task_id}",
    response_model=TaskStatus,
    responses=_DEFAULT_TASK_STATUS_CODES,
    description=create_route_description(
        base="Get task status",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10-rc1"),
        ],
    ),
    include_in_schema=True,
)
async def get_task_status(
    task_id: AsyncJobId,
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    task_manager = get_task_manager_from_app(app)

    try:
        task_status = await task_manager.get_task_status(
            task_filter=_get_task_filter(user_id, product_name),
            task_uuid=TaskUUID(f"{task_id}"),
        )
    except CeleryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encountered issue when getting task status",
        ) from exc

    return TaskStatus(
        task_progress=TaskProgress(
            task_id=f"{task_status.task_uuid}",
            percent=task_status.progress_report.percent_value,
        ),
        done=task_status.is_done,
        started=None,
    )


@router.post(
    "/{task_id}:cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_DEFAULT_TASK_STATUS_CODES,
    description=create_route_description(
        base="Cancel task",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10-rc1"),
        ],
    ),
    include_in_schema=True,
)
async def cancel_task(
    task_id: AsyncJobId,
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    task_manager = get_task_manager_from_app(app)

    try:
        await task_manager.cancel_task(
            task_filter=_get_task_filter(user_id, product_name),
            task_uuid=TaskUUID(f"{task_id}"),
        )
    except CeleryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encountered issue when cancelling task",
        ) from exc


@router.get(
    "/{task_id}/result",
    response_model=TaskResult,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Task result not found",
            "model": ErrorGet,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Task is cancelled",
            "model": ErrorGet,
        },
        **_DEFAULT_TASK_STATUS_CODES,
    },
    description=create_route_description(
        base="Get task result",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10-rc1"),
        ],
    ),
    include_in_schema=True,
)
async def get_task_result(
    task_id: AsyncJobId,
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    task_manager = get_task_manager_from_app(app)
    task_filter = _get_task_filter(user_id, product_name)

    try:
        # First check if task exists and is done
        task_status = await task_manager.get_task_status(
            task_filter=task_filter,
            task_uuid=TaskUUID(f"{task_id}"),
        )

        if not task_status.is_done:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task result not available yet",
            )

        result = await task_manager.get_task_result(
            task_filter=task_filter,
            task_uuid=TaskUUID(f"{task_id}"),
        )
        return TaskResult(result=result, error=None)

    except CeleryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encountered issue when getting task result",
        ) from exc
