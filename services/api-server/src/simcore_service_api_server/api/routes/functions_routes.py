from collections.abc import Callable
from typing import Annotated, Final, TypeAlias

import jsonschema
from fastapi import APIRouter, Depends, Header, Request, status
from fastapi_pagination.api import create_page
from jsonschema import ValidationError
from models_library.api_schemas_api_server.functions import (
    Function,
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionJobCollection,
    FunctionOutputSchema,
    FunctionSchemaClass,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    SolverFunctionJob,
)
from models_library.functions import FunctionUserAccessRights
from models_library.functions_errors import (
    FunctionExecuteAccessDeniedError,
    FunctionInputsValidationError,
    FunctionsExecuteApiAccessDeniedError,
    UnsupportedFunctionClassError,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import StringConstraints
from servicelib.fastapi.dependencies import get_reverse_url_mapper
from simcore_service_api_server._service_jobs import JobService

from ..._service_solvers import SolverService
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.jobs import JobInputs
from ...services_http.director_v2 import DirectorV2Api
from ...services_http.webserver import AuthSession
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.services import get_api_client, get_job_service, get_solver_service
from ..dependencies.webserver_http import get_webserver_session
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from . import solvers_jobs, studies_jobs
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)
from .function_jobs_routes import register_function_job

# pylint: disable=too-many-arguments
# pylint: disable=cyclic-import

NullString: TypeAlias = Annotated[str, StringConstraints(pattern="^null$")]

function_router = APIRouter()

_COMMON_FUNCTION_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function not found",
        "model": ErrorGet,
    },
}


ENDPOINTS = [
    "register_function",
    "get_function",
    "list_functions",
    "list_function_jobs_for_functionid",
    "update_function_title",
    "update_function_description",
    "get_function_inputschema",
    "get_function_outputschema",
    "validate_function_inputs",
    "run_function",
    "delete_function",
    "map_function",
]
CHANGE_LOGS = {}
for endpoint in ENDPOINTS:
    CHANGE_LOGS[endpoint] = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format("0.8.0"),
    ]
    if endpoint in [
        "register_function",
        "get_function",
        "list_functions",
        "list_function_jobs_for_functionid",
        "update_function_title",
        "update_function_description",
        "run_function",
        "map_function",
    ]:
        CHANGE_LOGS[endpoint].append(
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.9.0",
                "add `created_at` field in the registered function-related objects",
            )
        )


@function_router.post(
    "",
    response_model=RegisteredFunction,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Create function",
        changelog=CHANGE_LOGS["register_function"],
    ),
)
async def register_function(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    function: Function,
) -> RegisteredFunction:
    return await wb_api_rpc.register_function(
        user_id=user_id, product_name=product_name, function=function
    )


@function_router.get(
    "/{function_id:uuid}",
    response_model=RegisteredFunction,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function",
        changelog=CHANGE_LOGS["get_function"],
    ),
)
async def get_function(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunction:
    return await wb_api_rpc.get_function(
        function_id=function_id, user_id=user_id, product_name=product_name
    )


@function_router.get(
    "",
    response_model=Page[RegisteredFunction],
    description=create_route_description(
        base="List functions",
        changelog=CHANGE_LOGS["list_functions"],
    ),
)
async def list_functions(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    functions_list, meta = await wb_api_rpc.list_functions(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        user_id=user_id,
        product_name=product_name,
    )

    return create_page(
        functions_list,
        total=meta.total,
        params=page_params,
    )


@function_router.get(
    "/{function_id:uuid}/jobs",
    response_model=Page[RegisteredFunctionJob],
    description=create_route_description(
        base="List function jobs for a function",
        changelog=CHANGE_LOGS["list_function_jobs_for_functionid"],
    ),
)
async def list_function_jobs_for_functionid(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    function_jobs_list, meta = await wb_api_rpc.list_function_jobs(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        filter_by_function_id=function_id,
        user_id=user_id,
        product_name=product_name,
    )

    return create_page(
        function_jobs_list,
        total=meta.total,
        params=page_params,
    )


@function_router.patch(
    "/{function_id:uuid}/title",
    response_model=RegisteredFunction,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Update function",
        changelog=CHANGE_LOGS["update_function_title"],
    ),
)
async def update_function_title(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    title: str,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunction:
    returned_function = await wb_api_rpc.update_function_title(
        function_id=function_id, title=title, user_id=user_id, product_name=product_name
    )
    assert (
        returned_function.title == title
    ), f"Function title was not updated. Expected {title} but got {returned_function.title}"  # nosec
    return returned_function


@function_router.patch(
    "/{function_id:uuid}/description",
    response_model=RegisteredFunction,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Update function",
        changelog=CHANGE_LOGS["update_function_description"],
    ),
)
async def update_function_description(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    description: str,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunction:
    returned_function = await wb_api_rpc.update_function_description(
        function_id=function_id,
        description=description,
        user_id=user_id,
        product_name=product_name,
    )
    assert (
        returned_function.description == description
    ), f"Function description was not updated. Expected {description} but got {returned_function.description}"  # nosec
    return returned_function


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
    description=create_route_description(
        base="Get function input schema",
        changelog=CHANGE_LOGS["get_function_inputschema"],
    ),
)
async def get_function_inputschema(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> FunctionInputSchema:
    function = await wb_api_rpc.get_function(
        function_id=function_id, user_id=user_id, product_name=product_name
    )
    return function.input_schema


@function_router.get(
    "/{function_id:uuid}/output_schema",
    response_model=FunctionInputSchema,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function output schema",
        changelog=CHANGE_LOGS["get_function_outputschema"],
    ),
)
async def get_function_outputschema(
    function_id: FunctionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> FunctionOutputSchema:
    function = await wb_api_rpc.get_function(
        function_id=function_id, user_id=user_id, product_name=product_name
    )
    return function.output_schema


@function_router.post(
    "/{function_id:uuid}:validate_inputs",
    response_model=tuple[bool, str],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid inputs"},
        status.HTTP_404_NOT_FOUND: {"description": "Function not found"},
    },
    description=create_route_description(
        base="Validate inputs against the function's input schema",
        changelog=CHANGE_LOGS["validate_function_inputs"],
    ),
)
async def validate_function_inputs(
    function_id: FunctionID,
    inputs: FunctionInputs,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> tuple[bool, str]:
    function = await wb_api_rpc.get_function(
        function_id=function_id, user_id=user_id, product_name=product_name
    )

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
    description=create_route_description(
        base="Run function",
        changelog=CHANGE_LOGS["run_function"],
    ),
)
async def run_function(  # noqa: PLR0913
    request: Request,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    function_id: FunctionID,
    function_inputs: FunctionInputs,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    x_simcore_parent_project_uuid: Annotated[ProjectID | NullString, Header()],
    x_simcore_parent_node_id: Annotated[NodeID | NullString, Header()],
) -> RegisteredFunctionJob:

    parent_project_uuid = (
        x_simcore_parent_project_uuid
        if isinstance(x_simcore_parent_project_uuid, ProjectID)
        else None
    )
    parent_node_id = (
        x_simcore_parent_node_id
        if isinstance(x_simcore_parent_node_id, NodeID)
        else None
    )

    # Make sure the user is allowed to execute any function
    # (read/write right is checked in the other endpoint called in this method)
    user_api_access_rights = await wb_api_rpc.get_functions_user_api_access_rights(
        user_id=user_id, product_name=product_name
    )
    if not user_api_access_rights.execute_functions:
        raise FunctionsExecuteApiAccessDeniedError(
            user_id=user_id,
            function_id=function_id,
        )
    # Make sure the user is allowed to execute this particular function
    # (read/write right is checked in the other endpoint called in this method)
    user_permissions: FunctionUserAccessRights = (
        await wb_api_rpc.get_function_user_permissions(
            function_id=function_id, user_id=user_id, product_name=product_name
        )
    )
    if not user_permissions.execute:
        raise FunctionExecuteAccessDeniedError(
            user_id=user_id,
            function_id=function_id,
        )

    from .function_jobs_routes import function_job_status

    to_run_function = await wb_api_rpc.get_function(
        function_id=function_id, user_id=user_id, product_name=product_name
    )

    joined_inputs = _join_inputs(
        to_run_function.default_inputs,
        function_inputs,
    )

    if to_run_function.input_schema is not None:
        is_valid, validation_str = await validate_function_inputs(
            function_id=to_run_function.uid,
            inputs=joined_inputs,
            wb_api_rpc=wb_api_rpc,
            user_id=user_id,
            product_name=product_name,
        )
        if not is_valid:
            raise FunctionInputsValidationError(error=validation_str)

    if cached_function_jobs := await wb_api_rpc.find_cached_function_jobs(
        function_id=to_run_function.uid,
        inputs=joined_inputs,
        user_id=user_id,
        product_name=product_name,
    ):
        for cached_function_job in cached_function_jobs:
            job_status = await function_job_status(
                wb_api_rpc=wb_api_rpc,
                director2_api=director2_api,
                function_job_id=cached_function_job.uid,
                user_id=user_id,
                product_name=product_name,
            )
            if job_status.status == RunningState.SUCCESS:
                return cached_function_job

    if to_run_function.function_class == FunctionClass.PROJECT:
        study_job = await studies_jobs.create_study_job(
            study_id=to_run_function.project_id,
            job_inputs=JobInputs(values=joined_inputs or {}),
            webserver_api=webserver_api,
            wb_api_rpc=wb_api_rpc,
            url_for=url_for,
            x_simcore_parent_project_uuid=parent_project_uuid,
            x_simcore_parent_node_id=parent_node_id,
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
            user_id=user_id,
            product_name=product_name,
        )

    if to_run_function.function_class == FunctionClass.SOLVER:
        solver_job = await solvers_jobs.create_solver_job(
            solver_key=to_run_function.solver_key,
            version=to_run_function.solver_version,
            inputs=JobInputs(values=joined_inputs or {}),
            solver_service=solver_service,
            job_service=job_service,
            url_for=url_for,
            x_simcore_parent_project_uuid=parent_project_uuid,
            x_simcore_parent_node_id=parent_node_id,
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
            user_id=user_id,
            product_name=product_name,
        )

    raise UnsupportedFunctionClassError(
        function_class=to_run_function.function_class,
    )


@function_router.delete(
    "/{function_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Delete function",
        changelog=CHANGE_LOGS["delete_function"],
    ),
)
async def delete_function(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    function_id: FunctionID,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> None:
    return await wb_api_rpc.delete_function(
        function_id=function_id, user_id=user_id, product_name=product_name
    )


_COMMON_FUNCTION_JOB_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job not found",
        "model": ErrorGet,
    },
}


@function_router.post(
    "/{function_id:uuid}:map",
    response_model=RegisteredFunctionJobCollection,
    responses={**_COMMON_FUNCTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Map function over input parameters",
        changelog=CHANGE_LOGS["map_function"],
    ),
)
async def map_function(  # noqa: PLR0913
    function_id: FunctionID,
    function_inputs_list: FunctionInputsList,
    request: Request,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    solver_service: Annotated[SolverService, Depends(get_solver_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    x_simcore_parent_project_uuid: Annotated[ProjectID | NullString, Header()],
    x_simcore_parent_node_id: Annotated[NodeID | NullString, Header()],
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
            x_simcore_parent_project_uuid=x_simcore_parent_project_uuid,
            x_simcore_parent_node_id=x_simcore_parent_node_id,
        )
        for function_inputs in function_inputs_list
    ]

    function_job_collection_description = f"Function job collection of map of function {function_id} with {len(function_inputs_list)} inputs"
    # Import here to avoid circular import
    from .function_job_collections_routes import register_function_job_collection

    return await register_function_job_collection(
        wb_api_rpc=wb_api_rpc,
        function_job_collection=FunctionJobCollection(
            title="Function job collection of function map",
            description=function_job_collection_description,
            job_ids=[function_job.uid for function_job in function_jobs],
        ),
        user_id=user_id,
        product_name=product_name,
    )
