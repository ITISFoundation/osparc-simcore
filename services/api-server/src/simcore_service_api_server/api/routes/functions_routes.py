from collections.abc import Callable
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, status
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionJob,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    ProjectFunctionJob,
    SolverFunctionJob,
)
from pydantic import PositiveInt
from servicelib.fastapi.dependencies import get_reverse_url_mapper

from ...models.schemas.errors import ErrorGet
from ...models.schemas.jobs import (
    JobInputs,
)
from ...services_http.catalog import CatalogApi
from ...services_http.director_v2 import DirectorV2Api
from ...services_http.storage import StorageApi
from ...services_http.webserver import AuthSession
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.database import Engine, get_db_engine
from ..dependencies.services import get_api_client
from ..dependencies.webserver_http import get_webserver_session
from ..dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from . import solvers_jobs, solvers_jobs_getters, studies_jobs

function_router = APIRouter()
function_job_router = APIRouter()
function_job_collections_router = APIRouter()

_COMMON_FUNCTION_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function not found",
        "model": ErrorGet,
    },
}


@function_router.post("/ping")
async def ping(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.ping()


@function_router.get("", response_model=list[Function], description="List functions")
async def list_functions(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.list_functions()


@function_router.post("", response_model=Function, description="Create function")
async def register_function(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function: Function,
):
    return await wb_api_rpc.register_function(function=function)


@function_router.get(
    "/{function_id:uuid}",
    response_model=Function,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Get function",
)
async def get_function(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.get_function(function_id=function_id)


def join_inputs(
    default_inputs: FunctionInputs | None,
    function_inputs: FunctionInputs | None,
) -> FunctionInputs:
    if default_inputs is None:
        return function_inputs

    if function_inputs is None:
        return default_inputs

    # last dict will override defaults
    return {**default_inputs, **function_inputs}


@function_router.post(
    "/{function_id:uuid}:run",
    response_model=FunctionJob,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Run function",
)
async def run_function(
    request: Request,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    function_id: FunctionID,
    function_inputs: FunctionInputs,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
):

    to_run_function = await wb_api_rpc.get_function(function_id=function_id)

    assert to_run_function.uid is not None

    joined_inputs = join_inputs(
        to_run_function.default_inputs,
        function_inputs,
    )

    if cached_function_job := await wb_api_rpc.find_cached_function_job(
        function_id=to_run_function.uid,
        inputs=joined_inputs,
    ):
        return cached_function_job

    if to_run_function.function_class == FunctionClass.project:
        study_job = await studies_jobs.create_study_job(
            study_id=to_run_function.project_id,
            job_inputs=JobInputs(values=joined_inputs or {}),
            webserver_api=webserver_api,
            wb_api_rpc=wb_api_rpc,
            url_for=url_for,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            user_id=user_id,
            product_name=product_name,
        )
        await studies_jobs.start_study_job(
            request=request,
            study_id=to_run_function.project_id,
            job_id=study_job.id,
            user_id=user_id,
            webserver_api=webserver_api,
            director2_api=director2_api,
        )
        return await register_function_job(
            wb_api_rpc=wb_api_rpc,
            function_job=ProjectFunctionJob(
                function_uid=to_run_function.uid,
                title=f"Function job of function {to_run_function.uid}",
                description=to_run_function.description,
                inputs=joined_inputs,
                outputs=None,
                project_job_id=study_job.id,
            ),
        )
    elif to_run_function.function_class == FunctionClass.solver:  # noqa: RET505
        solver_job = await solvers_jobs.create_solver_job(
            solver_key=to_run_function.solver_key,
            version=to_run_function.solver_version,
            inputs=JobInputs(values=joined_inputs or {}),
            webserver_api=webserver_api,
            wb_api_rpc=wb_api_rpc,
            url_for=url_for,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            user_id=user_id,
            product_name=product_name,
            catalog_client=catalog_client,
        )
        await solvers_jobs.start_job(
            request=request,
            solver_key=to_run_function.solver_key,
            version=to_run_function.solver_version,
            job_id=solver_job.id,
            user_id=user_id,
            webserver_api=webserver_api,
            director2_api=director2_api,
        )
        return await register_function_job(
            wb_api_rpc=wb_api_rpc,
            function_job=SolverFunctionJob(
                function_uid=to_run_function.uid,
                title=f"Function job of function {to_run_function.uid}",
                description=to_run_function.description,
                inputs=joined_inputs,
                outputs=None,
                solver_job_id=solver_job.id,
            ),
        )
    else:
        msg = f"Function type {type(to_run_function)} not supported"
        raise TypeError(msg)


@function_router.delete(
    "/{function_id:uuid}",
    response_model=Function,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Delete function",
)
async def delete_function(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function_id: FunctionID,
):
    return await wb_api_rpc.delete_function(function_id=function_id)


@function_router.get(
    "/{function_id:uuid}/input_schema",
    response_model=FunctionInputSchema,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Get function",
)
async def get_function_input_schema(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function_id: FunctionID,
):
    return await wb_api_rpc.get_function_input_schema(function_id=function_id)


@function_router.get(
    "/{function_id:uuid}/output_schema",
    response_model=FunctionOutputSchema,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Get function",
)
async def get_function_output_schema(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function_id: FunctionID,
):
    return await wb_api_rpc.get_function_output_schema(function_id=function_id)


_COMMON_FUNCTION_JOB_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job not found",
        "model": ErrorGet,
    },
}


@function_job_router.post(
    "", response_model=FunctionJob, description="Create function job"
)
async def register_function_job(
    function_job: FunctionJob,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.register_function_job(function_job=function_job)


@function_job_router.get(
    "/{function_job_id:uuid}",
    response_model=FunctionJob,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description="Get function job",
)
async def get_function_job(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.get_function_job(function_job_id=function_job_id)


@function_job_router.get(
    "", response_model=list[FunctionJob], description="List function jobs"
)
async def list_function_jobs(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.list_function_jobs()


@function_job_router.delete(
    "/{function_job_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description="Delete function job",
)
async def delete_function_job(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.delete_function_job(function_job_id=function_job_id)


async def get_function_from_functionjobid(
    wb_api_rpc: WbApiRpcClient,
    function_job_id: FunctionJobID,
) -> tuple[Function, FunctionJob]:
    function_job = await get_function_job(
        wb_api_rpc=wb_api_rpc, function_job_id=function_job_id
    )

    return (
        await get_function(
            wb_api_rpc=wb_api_rpc, function_id=function_job.function_uid
        ),
        function_job,
    )


@function_job_router.get(
    "/{function_job_id:uuid}/status",
    response_model=FunctionJobStatus,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description="Get function job status",
)
async def function_job_status(
    function_job_id: FunctionJobID,
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc, function_job_id=function_job_id
    )

    if (
        function.function_class == FunctionClass.project
        and function_job.function_class == FunctionClass.project
    ):
        job_status = await studies_jobs.inspect_study_job(
            study_id=function.project_id,
            job_id=function_job.project_job_id,  # type: ignore
            user_id=user_id,
            director2_api=director2_api,
        )
        return FunctionJobStatus(status=job_status.state)
    elif (function.function_class == FunctionClass.solver) and (  # noqa: RET505
        function_job.function_class == FunctionClass.solver
    ):
        job_status = await solvers_jobs.inspect_job(
            solver_key=function.solver_key,
            version=function.solver_version,
            job_id=function_job.solver_job_id,
            user_id=user_id,
            director2_api=director2_api,
        )
        return FunctionJobStatus(status=job_status.state)
    else:
        msg = f"Function type {function.function_class} / Function job type {function_job.function_class} not supported"
        raise TypeError(msg)


@function_job_router.get(
    "/{function_job_id:uuid}/outputs",
    response_model=FunctionOutputs,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description="Get function job outputs",
)
async def function_job_outputs(
    function_job_id: FunctionJobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    db_engine: Annotated[Engine, Depends(get_db_engine)],
):
    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc, function_job_id=function_job_id
    )

    if (
        function.function_class == FunctionClass.project
        and function_job.function_class == FunctionClass.project
    ):
        job_outputs = await studies_jobs.get_study_job_outputs(
            study_id=function.project_id,
            job_id=function_job.project_job_id,  # type: ignore
            user_id=user_id,
            webserver_api=webserver_api,
            storage_client=storage_client,
        )

        return job_outputs.results
    elif (function.function_class == FunctionClass.solver) and (  # noqa: RET505
        function_job.function_class == FunctionClass.solver
    ):
        job_outputs = await solvers_jobs_getters.get_job_outputs(
            solver_key=function.solver_key,
            version=function.solver_version,
            job_id=function_job.solver_job_id,
            user_id=user_id,
            webserver_api=webserver_api,
            storage_client=storage_client,
            db_engine=db_engine,
        )
        return job_outputs.results
    else:
        msg = f"Function type {function.function_class} not supported"
        raise TypeError(msg)


@function_router.post(
    "/{function_id:uuid}:map",
    response_model=list[FunctionJob],
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Map function over input parameters",
)
async def map_function(
    function_id: FunctionID,
    function_inputs_list: FunctionInputsList,
    request: Request,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
):
    function_jobs = []
    for function_inputs in function_inputs_list:
        function_jobs = [
            await run_function(
                wb_api_rpc=wb_api_rpc,
                function_id=function_id,
                function_inputs=function_inputs,
                product_name=product_name,
                user_id=user_id,
                webserver_api=webserver_api,
                url_for=url_for,
                director2_api=director2_api,
                request=request,
                catalog_client=catalog_client,
            )
            for function_inputs in function_inputs_list
        ]
        # TODO poor system can't handle doing this in parallel, get this fixed  # noqa: FIX002
        # function_jobs = await asyncio.gather(*function_jobs_tasks)

    return function_jobs


# ruff: noqa: ERA001


# _logger = logging.getLogger(__name__)

# _COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES: Final[dict] = {
#     status.HTTP_404_NOT_FOUND: {
#         "description": "Function job collection not found",
#         "model": ErrorGet,
#     },
# }


# @function_job_collections_router.get(
#     "",
#     response_model=FunctionJobCollection,
#     description="List function job collections",
# )
# async def list_function_job_collections(
#     page_params: Annotated[PaginationParams, Depends()],
#     webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
# ):
#     msg = "list function jobs collection not implemented yet"
#     raise NotImplementedError(msg)


# @function_job_collections_router.post(
#     "", response_model=FunctionJobCollection, description="Create function job"
# )
# async def create_function_job_collection(
#     webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
#     job_ids: Annotated[list[FunctionJob], Depends()],
# ):
#     msg = "create function job collection not implemented yet"
#     raise NotImplementedError(msg)


# @function_job_collections_router.get(
#     "/{function_job_collection_id:uuid}",
#     response_model=FunctionJobCollection,
#     responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
#     description="Get function job",
# )
# async def get_function_job_collection(
#     function_job_collection_id: FunctionJobCollectionID,
#     webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
# ):
#     msg = "get function job collection not implemented yet"
#     raise NotImplementedError(msg)


# @function_job_collections_router.delete(
#     "/{function_job_collection_id:uuid}",
#     response_model=FunctionJob,
#     responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
#     description="Delete function job collection",
# )
# async def delete_function_job_collection(
#     function_job_collection_id: FunctionJobCollectionID,
#     webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
# ):
#     msg = "delete function job collection not implemented yet"
#     raise NotImplementedError(msg)


# @function_job_collections_router.get(
#     "/{function_job_collection_id:uuid}/function_jobs",
#     response_model=list[FunctionJob],
#     responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
#     description="Get the function jobs in function job collection",
# )
# async def function_job_collection_list_function_jobs(
#     function_job_collection_id: FunctionJobCollectionID,
#     webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
# ):
#     msg = "function job collection listing not implemented yet"
#     raise NotImplementedError(msg)


# @function_job_collections_router.get(
#     "/{function_job_collection_id:uuid}/status",
#     response_model=FunctionJobCollectionStatus,
#     responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
#     description="Get function job collection status",
# )
# async def function_job_collection_status(
#     function_job_collection_id: FunctionJobCollectionID,
#     webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
# ):
#     msg = "function job collection status not implemented yet"
#     raise NotImplementedError(msg)
