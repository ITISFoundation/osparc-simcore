import logging

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _groups_api
from ._exceptions_handlers import handle_plugin_requests_exceptions
from ._groups_api import WorkspaceGroupGet
from ._models import (
    WorkspacesGroupsBodyParams,
    WorkspacesGroupsPathParams,
    WorkspacesPathParams,
    WorkspacesRequestContext,
)

_logger = logging.getLogger(__name__)


#
# workspaces groups COLLECTION -------------------------
#

routes = web.RouteTableDef()


@routes.post(
    f"/{VTAG}/workspaces/{{workspace_id}}/groups/{{group_id}}",
    name="create_workspace_group",
)
@login_required
@permission_required("workspaces.*")
@handle_plugin_requests_exceptions
async def create_workspace_group(request: web.Request):
    req_ctx = WorkspacesRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(WorkspacesGroupsPathParams, request)
    body_params = await parse_request_body_as(WorkspacesGroupsBodyParams, request)

    workspace_groups: WorkspaceGroupGet = await _groups_api.create_workspace_group(
        request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(workspace_groups, web.HTTPCreated)


@routes.get(f"/{VTAG}/workspaces/{{workspace_id}}/groups", name="list_workspace_groups")
@login_required
@permission_required("workspaces.*")
@handle_plugin_requests_exceptions
async def list_workspace_groups(request: web.Request):
    req_ctx = WorkspacesRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)

    workspaces_groups: list[
        WorkspaceGroupGet
    ] = await _groups_api.list_workspace_groups_by_user_and_workspace(
        request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(workspaces_groups)


@routes.put(
    f"/{VTAG}/workspaces/{{workspace_id}}/groups/{{group_id}}",
    name="replace_workspace_group",
)
@login_required
@permission_required("workspaces.*")
@handle_plugin_requests_exceptions
async def replace_workspace_group(request: web.Request):
    req_ctx = WorkspacesRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(WorkspacesGroupsPathParams, request)
    body_params = await parse_request_body_as(WorkspacesGroupsBodyParams, request)

    workspace_group = await _groups_api.update_workspace_group(
        app=request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(workspace_group)


@routes.delete(
    f"/{VTAG}/workspaces/{{workspace_id}}/groups/{{group_id}}",
    name="delete_workspace_group",
)
@login_required
@permission_required("workspaces.*")
@handle_plugin_requests_exceptions
async def delete_workspace_group(request: web.Request):
    req_ctx = WorkspacesRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(WorkspacesGroupsPathParams, request)

    await _groups_api.delete_workspace_group(
        app=request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        group_id=path_params.group_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
