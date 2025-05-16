import asyncio
from typing import Annotated, Final

from fastapi import APIRouter, Depends, status
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.functions import (
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionStatus,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from pydantic import PositiveInt

from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...services_http.director_v2 import DirectorV2Api
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from .function_jobs_routes import function_job_status, get_function_job

# pylint: disable=too-many-arguments

function_job_collections_router = APIRouter()


_COMMON_FUNCTION_JOB_COLLECTION_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Function job collection not found",
        "model": ErrorGet,
    },
}


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
