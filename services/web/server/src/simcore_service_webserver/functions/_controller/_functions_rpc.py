from typing import Literal

from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.functions import (
    Function,
    FunctionAccessRights,
    FunctionClass,
    FunctionGroupAccessRights,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionUpdate,
    FunctionUserApiAccessRights,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredFunctionJobPatch,
    RegisteredFunctionJobWithStatus,
)
from models_library.functions_errors import (
    FunctionIDNotFoundError,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobCollectionReadAccessDeniedError,
    FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionJobCollectionsWriteApiAccessDeniedError,
    FunctionJobCollectionWriteAccessDeniedError,
    FunctionJobIDNotFoundError,
    FunctionJobPatchModelIncompatibleError,
    FunctionJobReadAccessDeniedError,
    FunctionJobsReadApiAccessDeniedError,
    FunctionJobsWriteApiAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
    FunctionReadAccessDeniedError,
    FunctionsReadApiAccessDeniedError,
    FunctionsWriteApiAccessDeniedError,
    FunctionWriteAccessDeniedError,
    UnsupportedFunctionClassError,
    UnsupportedFunctionJobClassError,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ...rabbitmq import get_rabbitmq_rpc_server
from .. import _functions_repository, _functions_service

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        UnsupportedFunctionClassError,
        FunctionsWriteApiAccessDeniedError,
    )
)
async def register_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function: Function,
) -> RegisteredFunction:
    return await _functions_service.register_function(
        app=app, user_id=user_id, product_name=product_name, function=function
    )


@router.expose(
    reraise_if_error_type=(
        UnsupportedFunctionJobClassError,
        FunctionJobsWriteApiAccessDeniedError,
    )
)
async def register_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job: FunctionJob,
) -> RegisteredFunctionJob:
    return await _functions_service.register_function_job(
        app=app, user_id=user_id, product_name=product_name, function_job=function_job
    )


@router.expose(
    reraise_if_error_type=(
        UnsupportedFunctionJobClassError,
        FunctionJobsWriteApiAccessDeniedError,
        FunctionJobPatchModelIncompatibleError,
    )
)
async def patch_registered_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_uuid: FunctionJobID,
    registered_function_job_patch: RegisteredFunctionJobPatch,
) -> RegisteredFunctionJob:

    return await _functions_service.patch_registered_function_job(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_uuid=function_job_uuid,
        registered_function_job_patch=registered_function_job_patch,
    )


@router.expose(reraise_if_error_type=(FunctionJobCollectionsWriteApiAccessDeniedError,))
async def register_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection: FunctionJobCollection,
) -> RegisteredFunctionJobCollection:
    return await _functions_service.register_function_job_collection(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_collection=function_job_collection,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionIDNotFoundError,
        FunctionReadAccessDeniedError,
        FunctionsReadApiAccessDeniedError,
    )
)
async def get_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> RegisteredFunction:
    return await _functions_service.get_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobIDNotFoundError,
        FunctionJobReadAccessDeniedError,
        FunctionJobsReadApiAccessDeniedError,
    )
)
async def get_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> RegisteredFunctionJob:
    return await _functions_service.get_function_job(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobCollectionIDNotFoundError,
        FunctionJobCollectionReadAccessDeniedError,
        FunctionJobCollectionsReadApiAccessDeniedError,
    )
)
async def get_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionJobID,
) -> RegisteredFunctionJobCollection:
    return await _functions_service.get_function_job_collection(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_collection_id=function_job_collection_id,
    )


@router.expose(reraise_if_error_type=(FunctionsReadApiAccessDeniedError,))
async def list_functions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    order_by: OrderBy | None = None,
    filter_by_function_class: FunctionClass | None = None,
    search_by_function_title: str | None = None,
    search_by_multi_columns: str | None = None,
) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
    return await _functions_service.list_functions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        order_by=order_by,
        filter_by_function_class=filter_by_function_class,
        search_by_function_title=search_by_function_title,
        search_by_multi_columns=search_by_multi_columns,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobsReadApiAccessDeniedError,
        FunctionsReadApiAccessDeniedError,
    )
)
async def list_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
    filter_by_function_job_ids: list[FunctionJobID] | None = None,
    filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
    return await _functions_service.list_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filter_by_function_id=filter_by_function_id,
        filter_by_function_job_ids=filter_by_function_job_ids,
        filter_by_function_job_collection_id=filter_by_function_job_collection_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobsReadApiAccessDeniedError,
        FunctionsReadApiAccessDeniedError,
    )
)
async def list_function_jobs_with_status(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
    filter_by_function_job_ids: list[FunctionJobID] | None = None,
    filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
) -> tuple[
    list[RegisteredFunctionJobWithStatus],
    PageMetaInfoLimitOffset,
]:
    return await _functions_service.list_function_jobs_with_status(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filter_by_function_id=filter_by_function_id,
        filter_by_function_job_ids=filter_by_function_job_ids,
        filter_by_function_job_collection_id=filter_by_function_job_collection_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobCollectionsReadApiAccessDeniedError,
        FunctionJobsReadApiAccessDeniedError,
        FunctionsReadApiAccessDeniedError,
    )
)
async def list_function_job_collections(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filters: FunctionJobCollectionsListFilters | None = None,
) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
    return await _functions_service.list_function_job_collections(
        app=app,
        user_id=user_id,
        product_name=product_name,
        pagination_limit=pagination_limit,
        pagination_offset=pagination_offset,
        filters=filters,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionIDNotFoundError,
        FunctionReadAccessDeniedError,
        FunctionWriteAccessDeniedError,
        FunctionsWriteApiAccessDeniedError,
        FunctionsReadApiAccessDeniedError,
    )
)
async def delete_function(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> None:
    return await _functions_repository.delete_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobIDNotFoundError,
        FunctionJobReadAccessDeniedError,
        FunctionJobWriteAccessDeniedError,
        FunctionJobsWriteApiAccessDeniedError,
    )
)
async def delete_function_job(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> None:
    return await _functions_repository.delete_function_job(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobCollectionIDNotFoundError,
        FunctionJobCollectionReadAccessDeniedError,
        FunctionJobCollectionWriteAccessDeniedError,
        FunctionJobCollectionsWriteApiAccessDeniedError,
    )
)
async def delete_function_job_collection(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionJobID,
) -> None:
    return await _functions_repository.delete_function_job_collection(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_collection_id=function_job_collection_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionIDNotFoundError,
        FunctionReadAccessDeniedError,
        FunctionWriteAccessDeniedError,
    )
)
async def update_function_title(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    title: str,
) -> RegisteredFunction:
    return await _functions_service.update_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        function=FunctionUpdate(title=title),
    )


@router.expose(
    reraise_if_error_type=(
        FunctionIDNotFoundError,
        FunctionReadAccessDeniedError,
        FunctionWriteAccessDeniedError,
    )
)
async def update_function_description(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    description: str,
) -> RegisteredFunction:
    return await _functions_service.update_function(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        function=FunctionUpdate(description=description),
    )


@router.expose()
async def find_cached_function_jobs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> list[RegisteredFunctionJob] | None:
    return await _functions_service.find_cached_function_jobs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
        inputs=inputs,
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_input_schema(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionInputSchema:
    return await _functions_service.get_function_input_schema(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobIDNotFoundError,))
async def get_function_job_status(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> FunctionJobStatus:
    return await _functions_service.get_function_job_status(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


@router.expose(reraise_if_error_type=(FunctionJobIDNotFoundError,))
async def get_function_job_outputs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> FunctionOutputs:
    return await _functions_service.get_function_job_outputs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobIDNotFoundError,
        FunctionJobWriteAccessDeniedError,
        FunctionJobReadAccessDeniedError,
    )
)
async def update_function_job_status(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
    job_status: FunctionJobStatus,
    check_write_permissions: bool = True,
) -> FunctionJobStatus:
    return await _functions_service.update_function_job_status(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
        job_status=job_status,
        check_write_permissions=check_write_permissions,
    )


@router.expose(
    reraise_if_error_type=(
        FunctionJobIDNotFoundError,
        FunctionJobWriteAccessDeniedError,
        FunctionJobReadAccessDeniedError,
    )
)
async def update_function_job_outputs(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
    outputs: FunctionOutputs,
    check_write_permissions: bool = True,
) -> FunctionOutputs:
    return await _functions_service.update_function_job_outputs(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_job_id=function_job_id,
        outputs=outputs,
        check_write_permissions=check_write_permissions,
    )


@router.expose(reraise_if_error_type=(FunctionIDNotFoundError,))
async def get_function_output_schema(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionOutputSchema:
    return await _functions_service.get_function_output_schema(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )


@router.expose(reraise_if_error_type=())
async def get_function_user_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionAccessRights:
    """
    Returns a dictionary with the user's permissions for the function.
    """
    return await _functions_service.get_function_user_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )


@router.expose(reraise_if_error_type=())
async def get_functions_user_api_access_rights(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionUserApiAccessRights:
    """
    Returns a dictionary with the user's abilities for all function related objects.
    """
    return await _functions_service.get_functions_user_api_access_rights(
        app=app,
        user_id=user_id,
        product_name=product_name,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    # FIXME: should depend on the webserver instance!
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)


@router.expose(reraise_if_error_type=())
async def set_group_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[FunctionID | FunctionJobID | FunctionJobCollectionID],
    read: bool | None = None,
    write: bool | None = None,
    execute: bool | None = None,
) -> list[
    tuple[
        FunctionID | FunctionJobID | FunctionJobCollectionID, FunctionGroupAccessRights
    ]
]:
    return await _functions_service.set_group_permissions(
        app=app,
        user_id=user_id,
        permission_group_id=permission_group_id,
        product_name=product_name,
        object_type=object_type,
        object_ids=object_ids,
        read=read,
        write=write,
        execute=execute,
    )
