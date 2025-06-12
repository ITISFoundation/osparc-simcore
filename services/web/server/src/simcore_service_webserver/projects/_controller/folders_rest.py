import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from pydantic import BaseModel, ConfigDict, field_validator
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from ..._meta import api_version_prefix as VTAG
from ...login.decorators import login_required
from ...security.decorators import permission_required
from .. import _folders_service
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class _ProjectsFoldersPathParams(BaseModel):
    project_id: ProjectID
    folder_id: FolderID | None
    model_config = ConfigDict(extra="forbid")

    # validators
    _null_or_none_str_to_none_validator = field_validator("folder_id", mode="before")(
        null_or_none_str_to_none_validator
    )


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/folders/{{folder_id}}",
    name="replace_project_folder",
)
@login_required
@permission_required("project.folders.*")
@handle_plugin_requests_exceptions
async def replace_project_folder(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectsFoldersPathParams, request)

    await _folders_service.move_project_into_folder(
        app=request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        folder_id=path_params.folder_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
