from logging import getLogger
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi_pagination.api import create_page
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.functions import (
    FunctionClass,
    FunctionJob,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    RegisteredFunctionJob,
)
from models_library.functions import RegisteredFunction
from models_library.functions_errors import (
    UnsupportedFunctionClassError,
)
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.fastapi.dependencies import get_app

from ..._service_function_jobs import FunctionJobService
from ..._service_function_jobs_task_client import (
    FunctionJobTaskClientService,
)
from ..._service_functions import FunctionService
from ..._service_jobs import JobService
from ...models.domain.functions import PageRegisteredFunctionJobWithorWithoutStatus
from ...models.pagination import PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.functions import FunctionJobsListFilters
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.functions import (
    get_function_from_functionjob,
    get_function_job_dependency,
    get_stored_job_outputs,
)
from ..dependencies.models_schemas_function_filters import get_function_jobs_filters
from ..dependencies.services import (
    get_function_job_service,
    get_function_job_task_client_service,
    get_function_service,
    get_job_service,
)
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

_logger = getLogger(__name__)

# pylint: disable=too-many-arguments
# pylint: disable=cyclic-import


JOB_LIST_FILTER_PAGE_RELEASE_VERSION = "0.11.0"
JOB_LOG_RELEASE_VERSION = "0.11.0"
WITH_STATUS_RELEASE_VERSION = "0.13.0"

function_job_router = APIRouter()

_COMMON_FUNCTION_JOB_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job not found",
        "model": ErrorGet,
    },
}

ENDPOINTS = [
    "list_function_jobs",
    "register_function_job",
    "get_function_job",
    "delete_function_job",
    "function_job_status",
    "function_job_outputs",
]
CHANGE_LOGS = {}
for endpoint in ENDPOINTS:
    CHANGE_LOGS[endpoint] = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format("0.8.0"),
    ]
    if endpoint in ["list_function_jobs", "register_function_job", "get_function_job"]:
        CHANGE_LOGS[endpoint].append(
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.9.0",
                "add `created_at` field in the registered function-related objects",
            )
        )
    if endpoint == "list_function_jobs":
        CHANGE_LOGS[endpoint].append(
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                JOB_LIST_FILTER_PAGE_RELEASE_VERSION,
                "add filter by `function_id`, `function_job_ids` and `function_job_collection_id`",
            )
        )

    if endpoint in ["list_function_jobs"]:
        CHANGE_LOGS[endpoint].append(
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                WITH_STATUS_RELEASE_VERSION,
                "add include_status bool query parameter to list function jobs with their status",
            )
        )


@function_job_router.get(
    "",
    response_model=PageRegisteredFunctionJobWithorWithoutStatus,
    description=create_route_description(
        base="List function jobs", changelog=CHANGE_LOGS["list_function_jobs"]
    ),
)
async def list_function_jobs(
    page_params: Annotated[PaginationParams, Depends()],
    function_job_task_client_service: Annotated[
        FunctionJobTaskClientService, Depends(get_function_job_task_client_service)
    ],
    function_job_service: Annotated[
        FunctionJobService, Depends(get_function_job_service)
    ],
    filters: Annotated[FunctionJobsListFilters, Depends(get_function_jobs_filters)],
    include_status: Annotated[  # noqa: FBT002
        bool, Query(description="Include job status in response")
    ] = False,
):
    if include_status:
        (
            function_jobs_list_ws,
            meta,
        ) = await function_job_task_client_service.list_function_jobs_with_status(
            pagination_offset=page_params.offset,
            pagination_limit=page_params.limit,
            filter_by_function_job_ids=filters.function_job_ids,
            filter_by_function_job_collection_id=filters.function_job_collection_id,
            filter_by_function_id=filters.function_id,
        )
        return create_page(
            function_jobs_list_ws,
            total=meta.total,
            params=page_params,
        )

    function_jobs_list, meta = await function_job_service.list_function_jobs(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        filter_by_function_job_ids=filters.function_job_ids,
        filter_by_function_job_collection_id=filters.function_job_collection_id,
        filter_by_function_id=filters.function_id,
    )

    return create_page(
        function_jobs_list,
        total=meta.total,
        params=page_params,
    )


@function_job_router.post(
    "",
    response_model=RegisteredFunctionJob,
    description=create_route_description(
        base="Create function job",
        changelog=CHANGE_LOGS["register_function_job"],
    ),
)
async def register_function_job(
    function_job: FunctionJob,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunctionJob:
    registered_job = await wb_api_rpc.register_function_job(
        function_job=function_job, user_id=user_id, product_name=product_name
    )
    return registered_job


@function_job_router.get(
    "/{function_job_id:uuid}",
    response_model=RegisteredFunctionJob,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function job",
        changelog=CHANGE_LOGS["get_function_job"],
    ),
)
async def get_function_job(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunctionJob:
    return await wb_api_rpc.get_function_job(
        function_job_id=function_job_id, user_id=user_id, product_name=product_name
    )


@function_job_router.delete(
    "/{function_job_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description=create_route_description(
        base="Delete function job",
        changelog=CHANGE_LOGS["delete_function_job"],
    ),
)
async def delete_function_job(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> None:
    return await wb_api_rpc.delete_function_job(
        function_job_id=function_job_id, user_id=user_id, product_name=product_name
    )


@function_job_router.get(
    "/{function_job_id:uuid}/status",
    response_model=FunctionJobStatus,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function job status",
        changelog=CHANGE_LOGS["function_job_status"],
    ),
)
async def function_job_status(
    function_job: Annotated[
        RegisteredFunctionJob, Depends(get_function_job_dependency)
    ],
    function: Annotated[RegisteredFunction, Depends(get_function_from_functionjob)],
    function_job_task_client_service: Annotated[
        FunctionJobTaskClientService, Depends(get_function_job_task_client_service)
    ],
) -> FunctionJobStatus:
    return await function_job_task_client_service.inspect_function_job(
        function=function, function_job=function_job
    )


async def get_function_from_functionjobid(
    wb_api_rpc: WbApiRpcClient,
    function_job_id: FunctionJobID,
    function_service: Annotated[FunctionService, Depends(get_function_service)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> tuple[RegisteredFunction, RegisteredFunctionJob]:
    function_job = await get_function_job(
        wb_api_rpc=wb_api_rpc,
        function_job_id=function_job_id,
        user_id=user_id,
        product_name=product_name,
    )

    return (
        await function_service.get_function(
            function_id=function_job.function_uid,
        ),
        function_job,
    )


@function_job_router.get(
    "/{function_job_id:uuid}/outputs",
    response_model=FunctionOutputs,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function job outputs",
        changelog=CHANGE_LOGS["function_job_outputs"],
    ),
)
async def function_job_outputs(
    function_job: Annotated[
        RegisteredFunctionJob, Depends(get_function_job_dependency)
    ],
    function_job_task_client_service: Annotated[
        FunctionJobTaskClientService, Depends(get_function_job_task_client_service)
    ],
    function: Annotated[RegisteredFunction, Depends(get_function_from_functionjob)],
    stored_job_outputs: Annotated[FunctionOutputs, Depends(get_stored_job_outputs)],
) -> FunctionOutputs:
    return await function_job_task_client_service.function_job_outputs(
        function_job=function_job,
        function=function,
        stored_job_outputs=stored_job_outputs,
    )


@function_job_router.post(
    "/{function_job_id:uuid}/log",
    response_model=TaskGet,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function job logs task",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format(JOB_LOG_RELEASE_VERSION),
        ],
    ),
)
async def get_function_job_logs_task(
    function_job_id: FunctionJobID,
    app: Annotated[FastAPI, Depends(get_app)],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    function_service: Annotated[FunctionService, Depends(get_function_service)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc,
        function_job_id=function_job_id,
        function_service=function_service,
        user_id=user_id,
        product_name=product_name,
    )
    app_router = app.router

    if (
        function.function_class == FunctionClass.PROJECT
        and function_job.function_class == FunctionClass.PROJECT
    ):
        if function_job.project_job_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not find project job",
            )
        async_job_get = await job_service.start_log_export(
            job_id=function_job.project_job_id,
        )
        _task_uuid = f"{async_job_get.job_id}"
        return TaskGet(
            task_id=_task_uuid,
            task_name=async_job_get.job_name,
            status_href=app_router.url_path_for(
                "get_task_status", task_uuid=_task_uuid
            ),
            abort_href=app_router.url_path_for("cancel_task", task_uuid=_task_uuid),
            result_href=app_router.url_path_for(
                "get_task_result", task_uuid=_task_uuid
            ),
        )

    if (
        function.function_class == FunctionClass.SOLVER
        and function_job.function_class == FunctionClass.SOLVER
    ):
        if function_job.solver_job_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not find solver job",
            )
        async_job_get = await job_service.start_log_export(
            job_id=function_job.solver_job_id,
        )
        _task_uuid = f"{async_job_get.job_id}"
        return TaskGet(
            task_id=_task_uuid,
            task_name=async_job_get.job_name,
            status_href=app_router.url_path_for(
                "get_task_status", task_uuid=_task_uuid
            ),
            abort_href=app_router.url_path_for("cancel_task", task_uuid=_task_uuid),
            result_href=app_router.url_path_for(
                "get_task_result", task_uuid=_task_uuid
            ),
        )
    raise UnsupportedFunctionClassError(function_class=function.function_class)
