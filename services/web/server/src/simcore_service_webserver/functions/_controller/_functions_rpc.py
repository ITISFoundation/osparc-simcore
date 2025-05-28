from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.functions import (
    Function,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionOutputSchema,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from models_library.functions_errors import (
    FunctionIDNotFoundError,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobCollectionReadAccessDeniedError,
    FunctionJobIDNotFoundError,
    FunctionJobReadAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
    FunctionReadAccessDeniedError,
    FunctionWriteAccessDeniedError,
    UnsupportedFunctionClassError,
    UnsupportedFunctionJobClassError,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ...rabbitmq import get_rabbitmq_rpc_server
from .. import _functions_repository, _functions_service

router = RPCRouter()


@router.expose(reraise_if_error_type=(UnsupportedFunctionClassError,))
async def register_function(
    app: web.Application, *, user_id: UserID, function: Function
) -> RegisteredFunction:
    return await _functions_service.register_function(
        app=app, user_id=user_id, function=function
    )


@router.expose(reraise_if_error_type=(UnsupportedFunctionJobClassError,))
async def register_function_job(
    app: web.Application, *, user_id: UserID, function_job: FunctionJob
) -> RegisteredFunctionJob:
    return await _functions_service.register_function_job(
        app=app, user_id=user_id, function_job=function_job
    )


@router.expose(reraise_if_error_type=())
async def register_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    function_job_collection: FunctionJobCollection,
) -> RegisteredFunctionJobCollection:
    return await _functions_service.register_function_job_collection(
        app=app, user_id=user_id, function_job_collection=function_job_collection
    )


@router.expose(
    reraise_if_error_type=(FunctionIDNotFoundError, FunctionReadAccessDeniedError)
)
async def get_function(
    app: web.Application, *, user_id: UserID, function_id: FunctionID
) -> RegisteredFunction:
    return await _functions_service.get_function(
        app=app,
        user_id=user_id,
        function_id=function_id,
    )


@router.expose(
    reraise_if_error_type=(FunctionJobIDNotFoundError, FunctionJobReadAccessDeniedError)
)
async def get_function_job(
    app: web.Application, *, user_id: UserID, function_job_id: FunctionJobID
) -> RegisteredFunctionJob:
    return await _functions_service.get_function_job(
        app=app,
        user_id=user_id,
        function_job_id=function_job_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobCollectionIDNotFoundError,
        FunctionJobCollectionReadAccessDeniedError,
    )
)
async def get_function_job_collection(
    app: web.Application, *, user_id: UserID, function_job_collection_id: FunctionJobID
) -> RegisteredFunctionJobCollection:
    return await _functions_service.get_function_job_collection(
        app=app,
        user_id=user_id,
        function_job_collection_id=function_job_collection_id,
    )


@router.expose()
async def list_functions(
    app: web.Application,
    *,
    user_id: UserID,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
    return await _functions_service.list_functions(
        app=app,
        user_id=user_id,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
    )


@router.expose()
async def list_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
    return await _functions_service.list_function_jobs(
        app=app,
        user_id=user_id,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filter_by_function_id=filter_by_function_id,
    )


@router.expose()
async def list_function_job_collections(
    app: web.Application,
    *,
    user_id: UserID,
    pagination_limit: int,
    pagination_offset: int,
    filters: FunctionJobCollectionsListFilters | None = None,
) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
    return await _functions_service.list_function_job_collections(
        app=app,
        user_id=user_id,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filters=filters,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionIDNotFoundError,
        FunctionReadAccessDeniedError,
        FunctionWriteAccessDeniedError,
    )
)
async def delete_function(
    app: web.Application, *, user_id: UserID, function_id: FunctionID
) -> None:
    return await _functions_repository.delete_function(
        app=app,
        user_id=user_id,
        function_id=function_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobIDNotFoundError,
        FunctionJobReadAccessDeniedError,
        FunctionJobWriteAccessDeniedError,
    )
)
async def delete_function_job(
    app: web.Application, *, user_id: UserID, function_job_id: FunctionJobID
) -> None:
    return await _functions_repository.delete_function_job(
        app=app,
        user_id=user_id,
        function_job_id=function_job_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobCollectionIDNotFoundError,))
async def delete_function_job_collection(
    app: web.Application, *, user_id: UserID, function_job_collection_id: FunctionJobID
) -> None:
    return await _functions_repository.delete_function_job_collection(
        app=app,
        user_id=user_id,
        function_job_collection_id=function_job_collection_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionIDNotFoundError,
        FunctionReadAccessDeniedError,
    )
)
async def update_function_title(
    app: web.Application, *, user_id: UserID, function_id: FunctionID, title: str
) -> RegisteredFunction:
    return await _functions_service.update_function_title(
        app=app,
        user_id=user_id,
        function_id=function_id,
        title=title,
    )


@router.expose(
    reraise_if_error_type=(FunctionIDNotFoundError, FunctionReadAccessDeniedError)
)
async def update_function_description(
    app: web.Application, *, user_id: UserID, function_id: FunctionID, description: str
) -> RegisteredFunction:
    return await _functions_service.update_function_description(
        app=app,
        user_id=user_id,
        function_id=function_id,
        description=description,
    )


@router.expose()
async def find_cached_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> FunctionJob | None:
    return await _functions_service.find_cached_function_job(
        app=app,
        user_id=user_id,
        function_id=function_id,
        inputs=inputs,
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_input_schema(
    app: web.Application, *, user_id: UserID, function_id: FunctionID
) -> FunctionInputSchema:
    return await _functions_service.get_function_input_schema(
        app=app,
        user_id=user_id,
        function_id=function_id,
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_output_schema(
    app: web.Application, *, user_id: UserID, function_id: FunctionID
) -> FunctionOutputSchema:
    return await _functions_service.get_function_output_schema(
        app=app,
        user_id=user_id,
        function_id=function_id,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
