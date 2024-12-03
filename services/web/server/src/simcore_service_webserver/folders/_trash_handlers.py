import logging

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from .._meta import API_VTAG as VTAG
from ..login.decorators import get_user_id, login_required
from ..products.api import get_product_name
from ..security.decorators import permission_required
from . import _trash_api
from ._exceptions_handlers import handle_plugin_requests_exceptions
from ._models import FoldersPathParams, FolderTrashQueryParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/folders/{{folder_id}}:trash", name="trash_folder")
@login_required
@permission_required("folder.delete")
@handle_plugin_requests_exceptions
async def trash_folder(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)
    query_params: FolderTrashQueryParams = parse_request_query_parameters_as(
        FolderTrashQueryParams, request
    )

    await _trash_api.trash_folder(
        request.app,
        product_name=product_name,
        user_id=user_id,
        folder_id=path_params.folder_id,
        force_stop_first=query_params.force,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{VTAG}/folders/{{folder_id}}:untrash", name="untrash_folder")
@login_required
@permission_required("folder.delete")
@handle_plugin_requests_exceptions
async def untrash_folder(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    await _trash_api.untrash_folder(
        request.app,
        product_name=product_name,
        user_id=user_id,
        folder_id=path_params.folder_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
