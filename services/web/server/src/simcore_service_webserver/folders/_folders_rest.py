import logging

from aiohttp import web
from models_library.api_schemas_webserver.folders_v2 import (
    FolderCreateBodyParams,
    FolderGet,
    FolderReplaceBodyParams,
)
from models_library.folders import FolderTuple
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import create_json_response_from_page, envelope_json_response
from . import _folders_service
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.models import (
    FolderFilters,
    FolderSearchQueryParams,
    FoldersListQueryParams,
    FoldersPathParams,
    FoldersRequestContext,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/folders", name="create_folder")
@login_required
@permission_required("folder.create")
@handle_plugin_requests_exceptions
async def create_folder(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    body_params = await parse_request_body_as(FolderCreateBodyParams, request)

    folder: FolderTuple = await _folders_service.create_folder(
        request.app,
        user_id=req_ctx.user_id,
        name=body_params.name,
        parent_folder_id=body_params.parent_folder_id,
        product_name=req_ctx.product_name,
        workspace_id=body_params.workspace_id,
    )

    return envelope_json_response(
        FolderGet.from_domain_model(
            folder.folder_db,
            trashed_by_primary_gid=None,
            user_folder_access_rights=folder.my_access_rights,
        ),
        web.HTTPCreated,
    )


@routes.get(f"/{VTAG}/folders", name="list_folders")
@login_required
@permission_required("folder.read")
@handle_plugin_requests_exceptions
async def list_folders(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    query_params: FoldersListQueryParams = parse_request_query_parameters_as(
        FoldersListQueryParams, request
    )

    if not query_params.filters:
        query_params.filters = FolderFilters()

    folders, total_count = await _folders_service.list_folders(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        folder_id=query_params.folder_id,
        workspace_id=query_params.workspace_id,
        trashed=query_params.filters.trashed,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )

    page = Page[FolderGet].model_validate(
        paginate_data(
            chunk=[FolderGet.from_domain_model(*f) for f in folders],
            request_url=request.url,
            total=total_count,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return create_json_response_from_page(page)


@routes.get(f"/{VTAG}/folders:search", name="list_folders_full_search")
@login_required
@permission_required("folder.read")
@handle_plugin_requests_exceptions
async def list_folders_full_search(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    query_params: FolderSearchQueryParams = parse_request_query_parameters_as(
        FolderSearchQueryParams, request
    )

    if not query_params.filters:
        query_params.filters = FolderFilters()

    folders, total_count = await _folders_service.list_folders_full_depth(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        text=query_params.text,
        trashed=query_params.filters.trashed,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )

    page = Page[FolderGet].model_validate(
        paginate_data(
            chunk=[FolderGet.from_domain_model(*f) for f in folders],
            request_url=request.url,
            total=total_count,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return create_json_response_from_page(page)


@routes.get(f"/{VTAG}/folders/{{folder_id}}", name="get_folder")
@login_required
@permission_required("folder.read")
@handle_plugin_requests_exceptions
async def get_folder(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    folder: FolderTuple = await _folders_service.get_folder(
        app=request.app,
        folder_id=path_params.folder_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(
        FolderGet.from_domain_model(
            folder.folder_db,
            folder.trashed_by_primary_gid,
            user_folder_access_rights=folder.my_access_rights,
        )
    )


@routes.put(
    f"/{VTAG}/folders/{{folder_id}}",
    name="replace_folder",
)
@login_required
@permission_required("folder.update")
@handle_plugin_requests_exceptions
async def replace_folder(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)
    body_params = await parse_request_body_as(FolderReplaceBodyParams, request)

    folder: FolderTuple = await _folders_service.update_folder(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        name=body_params.name,
        parent_folder_id=body_params.parent_folder_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(
        FolderGet.from_domain_model(
            folder.folder_db,
            folder.trashed_by_primary_gid,
            user_folder_access_rights=folder.my_access_rights,
        )
    )


@routes.delete(
    f"/{VTAG}/folders/{{folder_id}}",
    name="delete_folder",
)
@login_required
@permission_required("folder.delete")
@handle_plugin_requests_exceptions
async def delete_folder(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    await _folders_service.delete_folder_with_all_content(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
