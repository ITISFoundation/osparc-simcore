# pylint: disable=too-many-positional-arguments
from collections.abc import Callable
from typing import Annotated, Final, Literal

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi_pagination.api import create_page
from fastapi_pagination.bases import AbstractPage
from models_library.api_schemas_api_server.functions import (
    Function,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionOutputSchema,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from models_library.functions import FunctionJobCollection
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.fastapi.dependencies import get_reverse_url_mapper

from ..._service_function_jobs import FunctionJobService
from ..._service_function_jobs_task_client import FunctionJobTaskClientService
from ..._service_functions import FunctionService
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.jobs import JobInputs, JobPricingSpecification
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import (
    Identity,
    get_current_identity,
    get_current_user_id,
    get_product_name,
)
from ..dependencies.services import (
    get_function_job_service,
    get_function_job_task_client_service,
    get_function_service,
)
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)

# pylint: disable=too-many-arguments
# pylint: disable=cyclic-import

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
    return await wb_api_rpc.register_function(user_id=user_id, product_name=product_name, function=function)


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
    function_service: Annotated[FunctionService, Depends(get_function_service)],
) -> RegisteredFunction:
    return await function_service.get_function(
        function_id=function_id,
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
    function_service: Annotated[FunctionService, Depends(get_function_service)],
    page_params: Annotated[PaginationParams, Depends()],
) -> AbstractPage[RegisteredFunction]:
    functions_list, meta = await function_service.list_functions(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
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
    function_job_service: Annotated[FunctionJobService, Depends(get_function_job_service)],
    page_params: Annotated[PaginationParams, Depends()],
) -> AbstractPage[RegisteredFunctionJob]:
    function_jobs_list, meta = await function_job_service.list_function_jobs(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        filter_by_function_id=function_id,
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
    assert returned_function.title == title, (
        f"Function title was not updated. Expected {title} but got {returned_function.title}"
    )  # nosec
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
    assert returned_function.description == description, (
        f"Function description was not updated. Expected {description} but got {returned_function.description}"
    )  # nosec
    return returned_function


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
    function = await wb_api_rpc.get_function(function_id=function_id, user_id=user_id, product_name=product_name)
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
    function = await wb_api_rpc.get_function(function_id=function_id, user_id=user_id, product_name=product_name)
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
    function_id: FunctionID,  # pylint: disable=unused-argument
    inputs: FunctionInputs,
    function: Annotated[RegisteredFunction, Depends(get_function)],
    function_job_service: Annotated[FunctionJobService, Depends(get_function_job_service)],
) -> tuple[bool, str]:
    return await function_job_service.validate_function_inputs(
        function=function,
        job_inputs=[JobInputs(values=inputs or {})],
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
async def run_function(
    request: Request,
    user_identity: Annotated[Identity, Depends(get_current_identity)],
    to_run_function: Annotated[RegisteredFunction, Depends(get_function)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    function_inputs: FunctionInputs,
    function_service: Annotated[FunctionService, Depends(get_function_service)],
    function_job_task_client_service: Annotated[
        FunctionJobTaskClientService, Depends(get_function_job_task_client_service)
    ],
    x_simcore_parent_project_uuid: Annotated[ProjectID | Literal["null"], Header()],
    x_simcore_parent_node_id: Annotated[NodeID | Literal["null"], Header()],
) -> RegisteredFunctionJob:
    # preprocess inputs
    parent_project_uuid = (
        x_simcore_parent_project_uuid if isinstance(x_simcore_parent_project_uuid, ProjectID) else None
    )
    parent_node_id = x_simcore_parent_node_id if isinstance(x_simcore_parent_node_id, NodeID) else None
    pricing_spec = JobPricingSpecification.create_from_headers(request.headers)

    await function_service.check_execute_function_permission(
        function=to_run_function,
    )
    job_links = await function_service.get_function_job_links(to_run_function, url_for)

    jobs = await function_job_task_client_service.create_function_job_creation_tasks(
        function=to_run_function,
        function_inputs=[function_inputs],
        user_identity=user_identity,
        pricing_spec=pricing_spec,
        job_links=job_links,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=parent_node_id,
    )
    assert len(jobs) == 1  # nosec
    return jobs[0]


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
    return await wb_api_rpc.delete_function(function_id=function_id, user_id=user_id, product_name=product_name)


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
async def map_function(
    request: Request,
    user_identity: Annotated[Identity, Depends(get_current_identity)],
    to_run_function: Annotated[RegisteredFunction, Depends(get_function)],
    function_inputs_list: FunctionInputsList,
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    function_job_task_client_service: Annotated[
        FunctionJobTaskClientService, Depends(get_function_job_task_client_service)
    ],
    function_service: Annotated[FunctionService, Depends(get_function_service)],
    web_api_rpc_client: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    x_simcore_parent_project_uuid: Annotated[ProjectID | Literal["null"], Header()],
    x_simcore_parent_node_id: Annotated[NodeID | Literal["null"], Header()],
) -> RegisteredFunctionJobCollection:
    parent_project_uuid = (
        x_simcore_parent_project_uuid if isinstance(x_simcore_parent_project_uuid, ProjectID) else None
    )
    parent_node_id = x_simcore_parent_node_id if isinstance(x_simcore_parent_node_id, NodeID) else None
    pricing_spec = JobPricingSpecification.create_from_headers(request.headers)

    await function_service.check_execute_function_permission(
        function=to_run_function,
    )
    job_links = await function_service.get_function_job_links(to_run_function, url_for)

    jobs = await function_job_task_client_service.create_function_job_creation_tasks(
        function=to_run_function,
        function_inputs=function_inputs_list,
        user_identity=user_identity,
        pricing_spec=pricing_spec,
        job_links=job_links,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=parent_node_id,
    )

    # At this point, all results are FunctionJobID since we've checked for exceptions
    function_job_collection_description = (
        f"Function job collection of map of function {to_run_function.uid} with {len(function_inputs_list)} inputs"
    )
    return await web_api_rpc_client.register_function_job_collection(
        function_job_collection=FunctionJobCollection(
            title="Function job collection of function map",
            description=function_job_collection_description,
            job_ids=[job.uid for job in jobs],
        ),
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
    )
