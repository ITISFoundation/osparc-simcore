import logging
from contextlib import contextmanager
from typing import Annotated, Any

from celery_library.errors import TaskNotFoundError
from common_library.error_codes import create_error_code
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobId,
)
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.celery.models import TaskState, TaskUUID
from servicelib.fastapi.dependencies import get_app

from ...exceptions.backend_errors import CeleryTaskNotFoundError
from ...models.domain.celery_models import (
    ApiServerOwnerMetadata,
)
from ...models.schemas.base import ApiServerEnvelope
from ...models.schemas.errors import ErrorGet
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.celery import get_task_manager
from ._constants import (
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

router = APIRouter()
_logger = logging.getLogger(__name__)


_DEFAULT_TASK_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal server error",
        "model": ErrorGet,
    },
}


@contextmanager
def _exception_mapper(task_uuid: TaskUUID):
    try:
        yield
    except TaskNotFoundError as exc:
        raise CeleryTaskNotFoundError(task_uuid=task_uuid) from exc


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
    task_manager = get_task_manager(app)
    owner_metadata = ApiServerOwnerMetadata(
        user_id=user_id,
        product_name=product_name,
    )
    tasks = await task_manager.list_tasks(
        owner_metadata=owner_metadata,
    )

    app_router = app.router
    data = [
        TaskGet(
            task_id=f"{task.uuid}",
            task_name=task.metadata.name,
            status_href=app_router.url_path_for(
                "get_task_status", task_uuid=f"{task.uuid}"
            ),
            abort_href=app_router.url_path_for("cancel_task", task_uuid=f"{task.uuid}"),
            result_href=app_router.url_path_for(
                "get_task_result", task_uuid=f"{task.uuid}"
            ),
        )
        for task in tasks
    ]
    return ApiServerEnvelope(data=data)


@router.get(
    "/{task_uuid}",
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
    task_uuid: AsyncJobId,
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    task_manager = get_task_manager(app)
    owner_metadata = ApiServerOwnerMetadata(
        user_id=user_id,
        product_name=product_name,
    )
    with _exception_mapper(task_uuid=task_uuid):
        task_status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=TaskUUID(f"{task_uuid}"),
        )

    return TaskStatus(
        task_progress=TaskProgress(
            task_id=f"{task_status.task_uuid}",
            percent=task_status.progress_report.percent_value,
        ),
        done=task_status.is_done,
        started=None,
    )


@router.post(
    "/{task_uuid}:cancel",
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
    task_uuid: AsyncJobId,
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    task_manager = get_task_manager(app)
    owner_metadata = ApiServerOwnerMetadata(
        user_id=user_id,
        product_name=product_name,
    )
    with _exception_mapper(task_uuid=task_uuid):
        await task_manager.cancel_task(
            owner_metadata=owner_metadata,
            task_uuid=TaskUUID(f"{task_uuid}"),
        )


@router.get(
    "/{task_uuid}/result",
    response_model=TaskResult,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Task result not found",
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
    task_uuid: AsyncJobId,
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    task_manager = get_task_manager(app)
    owner_metadata = ApiServerOwnerMetadata(
        user_id=user_id,
        product_name=product_name,
    )

    with _exception_mapper(task_uuid=task_uuid):
        task_status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=TaskUUID(f"{task_uuid}"),
        )

        if not task_status.is_done:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task result not available yet",
            )

        task_result = await task_manager.get_task_result(
            owner_metadata=owner_metadata,
            task_uuid=TaskUUID(f"{task_uuid}"),
        )

        if task_status.task_state == TaskState.FAILURE:
            assert isinstance(task_result, Exception)
            user_error_msg = f"The execution of task {task_uuid} failed"
            support_id = create_error_code(task_result)
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    user_error_msg,
                    error=task_result,
                    error_code=support_id,
                    tip="Unexpected error in Celery",
                )
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=user_error_msg,
            )

    return TaskResult(result=task_result, error=None)
