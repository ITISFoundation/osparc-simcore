import functools
import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.projects import ProjectID
from pydantic import BaseModel, Extra, validator
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _folders_api, projects_api
from ._common_models import RequestContext
from .exceptions import ProjectGroupNotFoundError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


def _handle_projects_folders_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectGroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except ProjectNotFoundError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


class _ProjectsFoldersPathParams(BaseModel):
    project_id: ProjectID
    folder_id: FolderID | None

    class Config:
        extra = Extra.forbid

    @validator("folder_id", pre=True, always=True)
    @classmethod
    def convert_null_to_none(cls, v):
        if v is None or v == "null" or v == "none":
            return None
        return v


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/folders/{{folder_id}}",
    name="replace_project_folder",
)
@login_required
@permission_required("project.access_rights.update")
@_handle_projects_folders_exceptions
async def replace_project_folder(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_ProjectsFoldersPathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    await _folders_api.replace_project_folder(
        app=request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        folder_id=path_params.folder_id,
        product_name=req_ctx.product_name,
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
