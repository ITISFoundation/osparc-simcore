from typing import Annotated, Final

from fastapi import APIRouter, Depends, status
from fastapi_pagination.api import create_page
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
    UnsupportedFunctionFunctionJobClassCombinationError,
)
from models_library.products import ProductName
from models_library.projects_state import RunningState
from models_library.users import UserID
from sqlalchemy.ext.asyncio import AsyncEngine

from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...services_http.director_v2 import DirectorV2Api
from ...services_http.storage import StorageApi
from ...services_http.webserver import AuthSession
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.database import get_db_asyncpg_engine
from ..dependencies.services import get_api_client
from ..dependencies.webserver_http import get_webserver_session
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from . import solvers_jobs, solvers_jobs_read, studies_jobs
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

# pylint: disable=too-many-arguments
# pylint: disable=cyclic-import


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


@function_job_router.get(
    "",
    response_model=Page[RegisteredFunctionJob],
    description=create_route_description(
        base="List function jobs", changelog=CHANGE_LOGS["list_function_jobs"]
    ),
)
async def list_function_jobs(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    function_jobs_list, meta = await wb_api_rpc.list_function_jobs(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        user_id=user_id,
        product_name=product_name,
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
    return await wb_api_rpc.register_function_job(
        function_job=function_job, user_id=user_id, product_name=product_name
    )


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
    function_job_id: FunctionJobID,
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> FunctionJobStatus:

    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc,
        function_job_id=function_job_id,
        user_id=user_id,
        product_name=product_name,
    )
    old_job_status = await wb_api_rpc.get_function_job_status(
        function_job_id=function_job.uid, user_id=user_id, product_name=product_name
    )

    if old_job_status.status in (RunningState.SUCCESS, RunningState.FAILED):
        return old_job_status

    if (
        function.function_class == FunctionClass.PROJECT
        and function_job.function_class == FunctionClass.PROJECT
    ):
        job_status = await studies_jobs.inspect_study_job(
            study_id=function.project_id,
            job_id=function_job.project_job_id,
            user_id=user_id,
            director2_api=director2_api,
        )
    elif (function.function_class == FunctionClass.SOLVER) and (
        function_job.function_class == FunctionClass.SOLVER
    ):
        job_status = await solvers_jobs.inspect_job(
            solver_key=function.solver_key,
            version=function.solver_version,
            job_id=function_job.solver_job_id,
            user_id=user_id,
            director2_api=director2_api,
        )
    else:
        raise UnsupportedFunctionFunctionJobClassCombinationError(
            function_class=function.function_class,
            function_job_class=function_job.function_class,
        )

    new_job_status = FunctionJobStatus(status=job_status.state)

    return await wb_api_rpc.update_function_job_status(
        function_job_id=function_job.uid,
        user_id=user_id,
        product_name=product_name,
        job_status=new_job_status,
    )


async def get_function_from_functionjobid(
    wb_api_rpc: WbApiRpcClient,
    function_job_id: FunctionJobID,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> tuple[RegisteredFunction, RegisteredFunctionJob]:
    function_job = await get_function_job(
        wb_api_rpc=wb_api_rpc,
        function_job_id=function_job_id,
        user_id=user_id,
        product_name=product_name,
    )

    from .functions_routes import get_function

    return (
        await get_function(
            wb_api_rpc=wb_api_rpc,
            function_id=function_job.function_uid,
            user_id=user_id,
            product_name=product_name,
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
async def get_function_job_outputs(
    function_job_id: FunctionJobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    async_pg_engine: Annotated[AsyncEngine, Depends(get_db_asyncpg_engine)],
) -> FunctionOutputs:
    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc,
        function_job_id=function_job_id,
        user_id=user_id,
        product_name=product_name,
    )

    old_job_outputs = await wb_api_rpc.get_function_job_outputs(
        function_job_id=function_job.uid, user_id=user_id, product_name=product_name
    )

    if old_job_outputs is not None:
        return old_job_outputs

    if (
        function.function_class == FunctionClass.PROJECT
        and function_job.function_class == FunctionClass.PROJECT
    ):
        new_outputs = dict(
            (
                await studies_jobs.get_study_job_outputs(
                    study_id=function.project_id,
                    job_id=function_job.project_job_id,
                    user_id=user_id,
                    webserver_api=webserver_api,
                    storage_client=storage_client,
                )
            ).results
        )
    elif (
        function.function_class == FunctionClass.SOLVER
        and function_job.function_class == FunctionClass.SOLVER
    ):
        new_outputs = dict(
            (
                await solvers_jobs_read.get_job_outputs(
                    solver_key=function.solver_key,
                    version=function.solver_version,
                    job_id=function_job.solver_job_id,
                    user_id=user_id,
                    webserver_api=webserver_api,
                    storage_client=storage_client,
                    async_pg_engine=async_pg_engine,
                )
            ).results
        )
    else:
        raise UnsupportedFunctionClassError(function_class=function.function_class)

    return await wb_api_rpc.update_function_job_outputs(
        function_job_id=function_job.uid,
        user_id=user_id,
        product_name=product_name,
        outputs=new_outputs,
    )
