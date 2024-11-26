import logging

from aiohttp import web
from models_library.api_schemas_webserver.folders_v2 import (
    FolderCreateBodyParams,
    FolderGet,
    FolderGetPage,
    FolderReplaceBodyParams,
)
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _folders_api
from ._exceptions_handlers import handle_plugin_requests_exceptions
from ._models import (
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

    folder = await _folders_api.create_folder(
        request.app,
        user_id=req_ctx.user_id,
        name=body_params.name,
        parent_folder_id=body_params.parent_folder_id,
        product_name=req_ctx.product_name,
        workspace_id=body_params.workspace_id,
    )

    return envelope_json_response(folder, web.HTTPCreated)


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

    folders: FolderGetPage = await _folders_api.list_folders(
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
            chunk=folders.items,
            request_url=request.url,
            total=folders.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


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

    folders: FolderGetPage = await _folders_api.list_folders_full_search(
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
            chunk=folders.items,
            request_url=request.url,
            total=folders.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(f"/{VTAG}/folders/{{folder_id}}", name="get_folder")
@login_required
@permission_required("folder.read")
@handle_plugin_requests_exceptions
async def get_folder(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    folder: FolderGet = await _folders_api.get_folder(
        app=request.app,
        folder_id=path_params.folder_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(folder)


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

    folder = await _folders_api.update_folder(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        name=body_params.name,
        parent_folder_id=body_params.parent_folder_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(folder)


@routes.delete(
    f"/{VTAG}/folders/{{folder_id}}",
    name="delete_folder",
)
@login_required
@permission_required("folder.delete")
@handle_plugin_requests_exceptions
async def delete_folder_group(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    await _folders_api.delete_folder(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
