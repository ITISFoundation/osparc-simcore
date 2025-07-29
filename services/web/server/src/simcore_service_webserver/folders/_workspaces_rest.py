import logging

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.rest_constants import X_CLIENT_SESSION_ID_HEADER

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _workspaces_repository
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.models import FoldersRequestContext, FolderWorkspacesPathParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(
    f"/{VTAG}/folders/{{folder_id}}/workspaces/{{workspace_id}}:move",
    name="move_folder_to_workspace",
)
@login_required
@permission_required("folder.update")
@handle_plugin_requests_exceptions
async def move_folder_to_workspace(request: web.Request):
    req_ctx = FoldersRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(FolderWorkspacesPathParams, request)

    client_session_id: str | None = request.headers.get(X_CLIENT_SESSION_ID_HEADER)

    await _workspaces_repository.move_folder_into_workspace(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        workspace_id=path_params.workspace_id,
        product_name=req_ctx.product_name,
        client_session_id=client_session_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
