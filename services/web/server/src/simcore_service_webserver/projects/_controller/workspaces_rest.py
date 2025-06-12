import logging
from typing import Annotated

from aiohttp import web
from models_library.projects import ProjectID
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from ..._meta import api_version_prefix as VTAG
from ...login.decorators import login_required
from ...security.decorators import permission_required
from .. import _workspaces_service
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class _ProjectWorkspacesPathParams(BaseModel):
    project_id: ProjectID
    workspace_id: Annotated[
        WorkspaceID | None, BeforeValidator(null_or_none_str_to_none_validator)
    ] = Field(default=None)

    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/workspaces/{{workspace_id}}:move",
    name="move_project_to_workspace",
)
@login_required
@permission_required("project.workspaces.*")
@handle_plugin_requests_exceptions
async def move_project_to_workspace(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectWorkspacesPathParams, request
    )

    await _workspaces_service.move_project_into_workspace(
        app=request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        workspace_id=path_params.workspace_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
