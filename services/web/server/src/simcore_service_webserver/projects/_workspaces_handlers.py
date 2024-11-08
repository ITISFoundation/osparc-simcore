import functools
import logging
from typing import Annotated

from aiohttp import web
from models_library.projects import ProjectID
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.aiohttp.typing_extension import Handler

from .._meta import api_version_prefix as VTAG
from ..folders.errors import FolderAccessForbiddenError, FolderNotFoundError
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..workspaces.errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError
from . import _workspaces_api
from ._common_models import RequestContext
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


def _handle_projects_workspaces_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (
            ProjectNotFoundError,
            FolderNotFoundError,
            WorkspaceNotFoundError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except (
            ProjectInvalidRightsError,
            FolderAccessForbiddenError,
            WorkspaceAccessForbiddenError,
        ) as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


class _ProjectWorkspacesPathParams(BaseModel):
    project_id: ProjectID
    workspace_id: Annotated[WorkspaceID | None, BeforeValidator(null_or_none_str_to_none_validator)] = Field(default=None)

    model_config = ConfigDict(extra="forbid")


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/workspaces/{{workspace_id}}",
    name="replace_project_workspace",
)
@login_required
@permission_required("project.workspaces.*")
@_handle_projects_workspaces_exceptions
async def replace_project_workspace(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectWorkspacesPathParams, request
    )

    await _workspaces_api.move_project_into_workspace(
        app=request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        workspace_id=path_params.workspace_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
