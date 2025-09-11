from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi_pagination.api import create_page
from fastapi_pagination.bases import AbstractPage
from models_library.api_schemas_webserver.functions import (
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobCollectionStatus,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.utils import limited_gather

from ..._service_function_jobs import FunctionJobService
from ..._service_function_jobs_task_client import (
    FunctionJobTaskClientService,
)
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.application import get_app
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.functions import (
    get_function_from_functionjobid,
)
from ..dependencies.models_schemas_function_filters import (
    get_function_job_collections_filters,
)
from ..dependencies.services import (
    get_function_job_service,
    get_function_job_task_client_service,
)
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)
from .function_jobs_routes import get_function_job

# pylint: disable=too-many-arguments

function_job_collections_router = APIRouter()

FIRST_RELEASE_VERSION = "0.8.0"
JOB_LIST_PAGE_RELEASE_VERSION = "0.11.0"

_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job collection not found",
        "model": ErrorGet,
    },
}

ENDPOINTS = [
    "list_function_job_collections",
    "register_function_job_collection",
    "get_function_job_collection",
    "delete_function_job_collection",
]
CHANGE_LOGS = {}
for endpoint in ENDPOINTS:
    CHANGE_LOGS[endpoint] = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION),
    ]
    if endpoint in [
        "list_function_job_collections",
        "register_function_job_collection",
        "get_function_job_collection",
        "function_job_collection_list_function_jobs",
    ]:
        CHANGE_LOGS[endpoint].append(
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.9.0",
                "add `created_at` field in the registered function-related objects",
            )
        )


@function_job_collections_router.get(
    "",
    response_model=Page[RegisteredFunctionJobCollection],
    description=create_route_description(
        base="List function job collections",
        changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION)],
    ),
)
async def list_function_job_collections(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    page_params: Annotated[PaginationParams, Depends()],
    filters: Annotated[
        FunctionJobCollectionsListFilters, Depends(get_function_job_collections_filters)
    ],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> AbstractPage[RegisteredFunctionJobCollection]:
    function_job_collection_list, meta = await wb_api_rpc.list_function_job_collections(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
        filters=filters,
        user_id=user_id,
        product_name=product_name,
    )
    return create_page(
        function_job_collection_list,
        total=meta.total,
        params=page_params,
    )


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}",
    response_model=RegisteredFunctionJobCollection,
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function job collection",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION),
        ],
    ),
)
async def get_function_job_collection(
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunctionJobCollection:
    return await wb_api_rpc.get_function_job_collection(
        function_job_collection_id=function_job_collection_id,
        user_id=user_id,
        product_name=product_name,
    )


@function_job_collections_router.post(
    "",
    response_model=RegisteredFunctionJobCollection,
    description=create_route_description(
        base="Register function job collection",
        changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION)],
    ),
)
async def register_function_job_collection(
    function_job_collection: FunctionJobCollection,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],  # Updated type
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunctionJobCollection:
    return await wb_api_rpc.register_function_job_collection(
        function_job_collection=function_job_collection,
        user_id=user_id,
        product_name=product_name,
    )


@function_job_collections_router.delete(
    "/{function_job_collection_id:uuid}",
    response_model=None,
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Delete function job collection",
        changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION)],
    ),
)
async def delete_function_job_collection(
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> None:
    return await wb_api_rpc.delete_function_job_collection(
        function_job_collection_id=function_job_collection_id,
        user_id=user_id,
        product_name=product_name,
    )


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}/function_jobs",
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Get the function jobs in function job collection",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION),
        ],
    ),
)
async def function_job_collection_list_function_jobs(
    function_job_collection_id: FunctionJobCollectionID,
    function_job_service: Annotated[
        FunctionJobService, Depends(get_function_job_service)
    ],
) -> list[RegisteredFunctionJob]:
    return await function_job_collection_list_function_jobs_list(
        function_job_collection_id=function_job_collection_id,
        function_job_service=function_job_service,
    )


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}/function_jobs/page",
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    response_model=Page[RegisteredFunctionJob],
    description=create_route_description(
        base="Get the function jobs in function job collection",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format(JOB_LIST_PAGE_RELEASE_VERSION),
        ],
    ),
)
async def function_job_collection_list_function_jobs_page(
    function_job_collection_id: FunctionJobCollectionID,
    function_job_service: Annotated[
        FunctionJobService, Depends(get_function_job_service)
    ],
    page_params: Annotated[PaginationParams, Depends()],
) -> AbstractPage[RegisteredFunctionJob]:
    function_jobs_list, meta = await function_job_service.list_function_jobs(
        filter_by_function_job_collection_id=function_job_collection_id,
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )
    return create_page(function_jobs_list, total=meta.total, params=page_params)


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}/function_jobs/list",
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Get the function jobs in function job collection",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format(JOB_LIST_PAGE_RELEASE_VERSION),
        ],
    ),
)
async def function_job_collection_list_function_jobs_list(
    function_job_collection_id: FunctionJobCollectionID,
    function_job_service: Annotated[
        FunctionJobService, Depends(get_function_job_service)
    ],
) -> list[RegisteredFunctionJob]:
    function_jobs_list, _ = await function_job_service.list_function_jobs(
        filter_by_function_job_collection_id=function_job_collection_id,
    )
    return function_jobs_list


@function_job_collections_router.get(
    "/{function_job_collection_id:uuid}/status",
    response_model=FunctionJobCollectionStatus,
    responses={**_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES},
    description=create_route_description(
        base="Get function job collection status",
        changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format(FIRST_RELEASE_VERSION)],
    ),
)
async def function_job_collection_status(
    app: Annotated[FastAPI, Depends(get_app)],
    function_job_collection_id: FunctionJobCollectionID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],  # Updated type
    product_name: Annotated[ProductName, Depends(get_product_name)],
    function_job_task_client_service: Annotated[
        FunctionJobTaskClientService, Depends(get_function_job_task_client_service)
    ],
) -> FunctionJobCollectionStatus:
    function_job_collection = await get_function_job_collection(
        function_job_collection_id=function_job_collection_id,
        wb_api_rpc=wb_api_rpc,
        user_id=user_id,
        product_name=product_name,
    )

    job_statuses = await limited_gather(
        *[
            function_job_task_client_service.inspect_function_job(
                function_job=await get_function_job(
                    function_job_id=function_job_id,
                    wb_api_rpc=wb_api_rpc,
                    user_id=user_id,
                    product_name=product_name,
                ),
                function=await get_function_from_functionjobid(
                    function_job_id=function_job_id,
                    wb_api_rpc=wb_api_rpc,
                    user_id=user_id,
                    product_name=product_name,
                ),
            )
            for function_job_id in function_job_collection.job_ids
        ]
    )
    return FunctionJobCollectionStatus(
        status=[job_status.status for job_status in job_statuses]
    )
