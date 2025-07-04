import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, status
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobId,
    AsyncJobNameData,
)
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.fastapi.dependencies import get_app

from ...models.schemas.base import ApiServerEnvelope
from ...models.schemas.errors import ErrorGet
from ...services_rpc.async_jobs import AsyncJobClient
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.tasks import get_async_jobs_client
from ._constants import (
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

router = APIRouter()
_logger = logging.getLogger(__name__)


def _get_job_id_data(user_id: UserID, product_name: ProductName) -> AsyncJobNameData:
    return AsyncJobNameData(user_id=user_id, product_name=product_name)


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
    include_in_schema=False,  # TO BE RELEASED in 0.10-rc1
)
async def list_tasks(
    app: Annotated[FastAPI, Depends(get_app)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    async_jobs: Annotated[AsyncJobClient, Depends(get_async_jobs_client)],
):
    user_async_jobs = await async_jobs.list_jobs(
        job_id_data=_get_job_id_data(user_id, product_name),
        filter_="",
    )
    app_router = app.router
    data = [
        TaskGet(
            task_id=f"{job.job_id}",
            task_name=job.job_name,
            status_href=app_router.url_path_for(
                "get_task_status", task_id=f"{job.job_id}"
            ),
            abort_href=app_router.url_path_for("cancel_task", task_id=f"{job.job_id}"),
            result_href=app_router.url_path_for(
                "get_task_result", task_id=f"{job.job_id}"
            ),
        )
        for job in user_async_jobs
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
    include_in_schema=False,  # TO BE RELEASED in 0.10-rc1
)
async def get_task_status(
    task_id: AsyncJobId,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    async_jobs: Annotated[AsyncJobClient, Depends(get_async_jobs_client)],
):
    async_job_rpc_status = await async_jobs.status(
        job_id=task_id,
        job_id_data=_get_job_id_data(user_id, product_name),
    )
    _task_id = f"{async_job_rpc_status.job_id}"
    return TaskStatus(
        task_progress=TaskProgress(
            task_id=_task_id, percent=async_job_rpc_status.progress.percent_value
        ),
        done=async_job_rpc_status.done,
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
    include_in_schema=False,  # TO BE RELEASED in 0.10-rc1
)
async def cancel_task(
    task_id: AsyncJobId,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    async_jobs: Annotated[AsyncJobClient, Depends(get_async_jobs_client)],
):
    await async_jobs.cancel(
        job_id=task_id,
        job_id_data=_get_job_id_data(user_id, product_name),
    )


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
    include_in_schema=False,  # TO BE RELEASED in 0.10-rc1
)
async def get_task_result(
    task_id: AsyncJobId,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    async_jobs: Annotated[AsyncJobClient, Depends(get_async_jobs_client)],
):
    async_job_rpc_result = await async_jobs.result(
        job_id=task_id,
        job_id_data=_get_job_id_data(user_id, product_name),
    )
    return TaskResult(result=async_job_rpc_result.result, error=None)
