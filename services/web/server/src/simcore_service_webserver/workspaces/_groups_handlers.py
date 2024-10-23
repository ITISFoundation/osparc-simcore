""" Handlers for project comments operations

"""

import functools
import logging

from aiohttp import web
from models_library.users import GroupID, UserID
from models_library.workspaces import WorkspaceID
from pydantic import ConfigDict, BaseModel, Field
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _groups_api
from ._groups_api import WorkspaceGroupGet
from ._workspaces_handlers import WorkspacesPathParams
from .errors import WorkspaceAccessForbiddenError, WorkspaceGroupNotFoundError

_logger = logging.getLogger(__name__)


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


def _handle_workspaces_groups_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WorkspaceGroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except WorkspaceAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# workspaces groups COLLECTION -------------------------
#

routes = web.RouteTableDef()


class _WorkspacesGroupsPathParams(BaseModel):
    workspace_id: WorkspaceID
    group_id: GroupID
    model_config = ConfigDict(extra="forbid")


class _WorkspacesGroupsBodyParams(BaseModel):
    read: bool
    write: bool
    delete: bool
    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{VTAG}/workspaces/{{workspace_id}}/groups/{{group_id}}",
    name="create_workspace_group",
)
@login_required
@permission_required("workspaces.*")
@_handle_workspaces_groups_exceptions
async def create_workspace_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_WorkspacesGroupsPathParams, request)
    body_params = await parse_request_body_as(_WorkspacesGroupsBodyParams, request)

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
@_handle_workspaces_groups_exceptions
async def list_workspace_groups(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)

    workspaces: list[
        WorkspaceGroupGet
    ] = await _groups_api.list_workspace_groups_by_user_and_workspace(
        request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(workspaces, web.HTTPOk)


@routes.put(
    f"/{VTAG}/workspaces/{{workspace_id}}/groups/{{group_id}}",
    name="replace_workspace_group",
)
@login_required
@permission_required("workspaces.*")
@_handle_workspaces_groups_exceptions
async def replace_workspace_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_WorkspacesGroupsPathParams, request)
    body_params = await parse_request_body_as(_WorkspacesGroupsBodyParams, request)

    return await _groups_api.update_workspace_group(
        app=request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )


@routes.delete(
    f"/{VTAG}/workspaces/{{workspace_id}}/groups/{{group_id}}",
    name="delete_workspace_group",
)
@login_required
@permission_required("workspaces.*")
@_handle_workspaces_groups_exceptions
async def delete_workspace_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_WorkspacesGroupsPathParams, request)

    await _groups_api.delete_workspace_group(
        app=request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        group_id=path_params.group_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
