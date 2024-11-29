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
from ._models import WorkspacesPathParams, WorkspaceTrashQueryParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/workspaces/{{workspace_id}}:trash", name="trash_workspace")
@login_required
@permission_required("workspaces.*")
@handle_plugin_requests_exceptions
async def trash_workspace(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)
    query_params: WorkspaceTrashQueryParams = parse_request_query_parameters_as(
        WorkspaceTrashQueryParams, request
    )

    await _trash_api.trash_workspace(
        request.app,
        product_name=product_name,
        user_id=user_id,
        workspace_id=path_params.workspace_id,
        force_stop_first=query_params.force,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{VTAG}/workspaces/{{workspace_id}}:untrash", name="untrash_workspace")
@login_required
@permission_required("workspaces.*")
@handle_plugin_requests_exceptions
async def untrash_workspace(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)

    await _trash_api.untrash_workspace(
        request.app,
        product_name=product_name,
        user_id=user_id,
        workspace_id=path_params.workspace_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
