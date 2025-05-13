import asyncio
from collections.abc import Callable
from typing import Annotated, Final

import jsonschema
from fastapi import APIRouter, Depends, Request, status
from fastapi_pagination.api import create_page
from jsonschema import ValidationError
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionInputsValidationError,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionStatus,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionSchemaClass,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    SolverFunctionJob,
    UnsupportedFunctionClassError,
    UnsupportedFunctionFunctionJobClassCombinationError,
)
from pydantic import PositiveInt
from servicelib.fastapi.dependencies import get_reverse_url_mapper
from simcore_service_api_server._service_jobs import JobService
from sqlalchemy.ext.asyncio import AsyncEngine

from ..._service_solvers import SolverService
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.jobs import JobInputs
from ...services_http.director_v2 import DirectorV2Api
from ...services_http.storage import StorageApi
from ...services_http.webserver import AuthSession
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.database import get_db_asyncpg_engine
from ..dependencies.services import get_api_client, get_job_service, get_solver_service
from ..dependencies.webserver_http import get_webserver_session
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from . import solvers_jobs, solvers_jobs_getters, studies_jobs

# pylint: disable=too-many-arguments,no-else-return

function_router = APIRouter()
function_job_router = APIRouter()
function_job_collections_router = APIRouter()

_COMMON_FUNCTION_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function not found",
        "model": ErrorGet,
    },
}


@function_router.post(
    "",
    response_model=RegisteredFunction,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Create function",
)
async def register_function(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function: Function,
) -> RegisteredFunction:
    return await wb_api_rpc.register_function(function=function)


@function_router.get(
    "/{function_id:uuid}",
    response_model=RegisteredFunction,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Get function",
)
async def get_function(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> RegisteredFunction:
    return await wb_api_rpc.get_function(function_id=function_id)


@function_router.get(
    "", response_model=Page[RegisteredFunction], description="List functions"
)
async def list_functions(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
):
    functions_list, meta = await wb_api_rpc.list_functions(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )

    return create_page(
        functions_list,
        total=meta.total,
        params=page_params,
    )


@function_job_router.get(
    "", response_model=Page[RegisteredFunctionJob], description="List function jobs"
)
async def list_function_jobs(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
):
    function_jobs_list, meta = await wb_api_rpc.list_function_jobs(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )

    return create_page(
        function_jobs_list,
        total=meta.total,
        params=page_params,
    )


@function_job_collections_router.get(
    "",
    response_model=Page[RegisteredFunctionJobCollection],
    description="List function job collections",
)
async def list_function_job_collections(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
):
    function_job_collection_list, meta = await wb_api_rpc.list_function_job_collections(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )
    return create_page(
        function_job_collection_list,
        total=meta.total,
        params=page_params,
    )


def _join_inputs(
    default_inputs: FunctionInputs | None,
    function_inputs: FunctionInputs | None,
) -> FunctionInputs:
    if default_inputs is None:
        return function_inputs

    if function_inputs is None:
        return default_inputs

    # last dict will override defaults
    return {**default_inputs, **function_inputs}


@function_router.get(
    "/{function_id:uuid}/input_schema",
    response_model=FunctionInputSchema,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Get function input schema",
)
async def get_function_inputschema(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> FunctionInputSchema:
    function = await wb_api_rpc.get_function(function_id=function_id)
    return function.input_schema


@function_router.get(
    "/{function_id:uuid}/output_schema",
    response_model=FunctionInputSchema,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Get function input schema",
)
async def get_function_outputschema(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> FunctionOutputSchema:
    function = await wb_api_rpc.get_function(function_id=function_id)
    return function.output_schema


@function_router.post(
    "/{function_id:uuid}:validate_inputs",
    response_model=tuple[bool, str],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid inputs"},
        status.HTTP_404_NOT_FOUND: {"description": "Function not found"},
    },
    description="Validate inputs against the function's input schema",
)
async def validate_function_inputs(
    function_id: FunctionID,
    inputs: FunctionInputs,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> tuple[bool, str]:
    function = await wb_api_rpc.get_function(function_id=function_id)

    if function.input_schema is None or function.input_schema.schema_content is None:
        return True, "No input schema defined for this function"

    if function.input_schema.schema_class == FunctionSchemaClass.json_schema:
        try:
            jsonschema.validate(
                instance=inputs, schema=function.input_schema.schema_content
            )
        except ValidationError as err:
            return False, str(err)
        return True, "Inputs are valid"

    return (
        False,
        f"Unsupported function schema class {function.input_schema.schema_class}",
    )


@function_router.post(
    "/{function_id:uuid}:run",
    response_model=RegisteredFunctionJob,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Run function",
)
async def run_function(  # noqa: PLR0913
    request: Request,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    function_id: FunctionID,
    function_inputs: FunctionInputs,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> RegisteredFunctionJob:

    to_run_function = await wb_api_rpc.get_function(function_id=function_id)

    joined_inputs = _join_inputs(
        to_run_function.default_inputs,
        function_inputs,
    )

    if to_run_function.input_schema is not None:
        is_valid, validation_str = await validate_function_inputs(
            function_id=to_run_function.uid,
            inputs=joined_inputs,
            wb_api_rpc=wb_api_rpc,
        )
        if not is_valid:
            raise FunctionInputsValidationError(error=validation_str)

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
            solver_service=solver_service,
            job_service=job_service,
            url_for=url_for,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
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
        raise UnsupportedFunctionClassError(
            function_class=to_run_function.function_class,
        )


@function_router.delete(
    "/{function_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Delete function",
)
async def delete_function(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function_id: FunctionID,
) -> None:
    return await wb_api_rpc.delete_function(function_id=function_id)


_COMMON_FUNCTION_JOB_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job not found",
        "model": ErrorGet,
    },
}


@function_job_router.post(
    "", response_model=RegisteredFunctionJob, description="Create function job"
)
async def register_function_job(
    function_job: FunctionJob,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> RegisteredFunctionJob:
    return await wb_api_rpc.register_function_job(function_job=function_job)


@function_job_router.get(
    "/{function_job_id:uuid}",
    response_model=RegisteredFunctionJob,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description="Get function job",
)
async def get_function_job(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> RegisteredFunctionJob:
    return await wb_api_rpc.get_function_job(function_job_id=function_job_id)


@function_job_router.delete(
    "/{function_job_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_JOB_ERROR_RESPONSES},
    description="Delete function job",
)
async def delete_function_job(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> None:
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
) -> FunctionJobStatus:
    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc, function_job_id=function_job_id
    )

    if (
        function.function_class == FunctionClass.project
        and function_job.function_class == FunctionClass.project
    ):
        job_status = await studies_jobs.inspect_study_job(
            study_id=function.project_id,
            job_id=function_job.project_job_id,
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
        raise UnsupportedFunctionFunctionJobClassCombinationError(
            function_class=function.function_class,
            function_job_class=function_job.function_class,
        )


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
    async_pg_engine: Annotated[AsyncEngine, Depends(get_db_asyncpg_engine)],
) -> FunctionOutputs:
    function, function_job = await get_function_from_functionjobid(
        wb_api_rpc=wb_api_rpc, function_job_id=function_job_id
    )

    if (
        function.function_class == FunctionClass.project
        and function_job.function_class == FunctionClass.project
    ):
        return dict(
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

    if (
        function.function_class == FunctionClass.solver
        and function_job.function_class == FunctionClass.solver
    ):
        return dict(
            (
                await solvers_jobs_getters.get_job_outputs(
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
    raise UnsupportedFunctionClassError(function_class=function.function_class)


@function_router.post(
    "/{function_id:uuid}:map",
    response_model=RegisteredFunctionJobCollection,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description="Map function over input parameters",
)
async def map_function(  # noqa: PLR0913
    function_id: FunctionID,
    function_inputs_list: FunctionInputsList,
    request: Request,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> RegisteredFunctionJobCollection:
    function_jobs = []
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
            solver_service=solver_service,
            job_service=job_service,
        )
        for function_inputs in function_inputs_list
    ]

    function_job_collection_description = f"Function job collection of map of function {function_id} with {len(function_inputs_list)} inputs"
    return await register_function_job_collection(
        wb_api_rpc=wb_api_rpc,
        function_job_collection=FunctionJobCollection(
            title="Function job collection of function map",
            description=function_job_collection_description,
            job_ids=[function_job.uid for function_job in function_jobs],
        ),
    )


_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job collection not found",
        "model": ErrorGet,
    },
}


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}",
    response_model=RegisteredFunctionJobCollection,
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description="Get function job collection",
)
async def get_function_job_collection(
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> RegisteredFunctionJobCollection:
    return await wb_api_rpc.get_function_job_collection(
        function_job_collection_id=function_job_collection_id
    )


@function_job_collections_router.post(
    "",
    response_model=RegisteredFunctionJobCollection,
    description="Register function job collection",
)
async def register_function_job_collection(
    function_job_collection: FunctionJobCollection,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> RegisteredFunctionJobCollection:
    return await wb_api_rpc.register_function_job_collection(
        function_job_collection=function_job_collection
    )


@function_job_collections_router.delete(
    "/{function_job_collection_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description="Delete function job collection",
)
async def delete_function_job_collection(
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> None:
    return await wb_api_rpc.delete_function_job_collection(
        function_job_collection_id=function_job_collection_id
    )


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}/function_jobs",
    response_model=list[RegisteredFunctionJob],
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description="Get the function jobs in function job collection",
)
async def function_job_collection_list_function_jobs(
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> list[RegisteredFunctionJob]:
    function_job_collection = await get_function_job_collection(
        function_job_collection_id=function_job_collection_id,
        wb_api_rpc=wb_api_rpc,
    )
    return [
        await get_function_job(
            job_id,
            wb_api_rpc=wb_api_rpc,
        )
        for job_id in function_job_collection.job_ids
    ]


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}/status",
    response_model=FunctionJobCollectionStatus,
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description="Get function job collection status",
)
async def function_job_collection_status(
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
) -> FunctionJobCollectionStatus:
    function_job_collection = await get_function_job_collection(
        function_job_collection_id=function_job_collection_id,
        wb_api_rpc=wb_api_rpc,
    )

    job_statuses = await asyncio.gather(
        *[
            function_job_status(
                job_id,
                wb_api_rpc=wb_api_rpc,
                director2_api=director2_api,
                user_id=user_id,
            )
            for job_id in function_job_collection.job_ids
        ]
    )
    return FunctionJobCollectionStatus(
        status=[job_status.status for job_status in job_statuses]
    )
