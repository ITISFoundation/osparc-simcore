""" Handlers for project comments operations

"""

import functools
import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.users import GroupID, UserID
from pydantic import BaseModel, Extra, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _groups_api
from ._folders_handlers import FoldersPathParams
from ._groups_api import FolderGroupGet
from .errors import FolderAccessForbiddenError, FolderGroupNotFoundError

_logger = logging.getLogger(__name__)


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


def _handle_folders_groups_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except FolderGroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except FolderAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# folders groups COLLECTION -------------------------
#

routes = web.RouteTableDef()


class _FoldersGroupsPathParams(BaseModel):
    folder_id: FolderID
    group_id: GroupID

    class Config:
        extra = Extra.forbid


class _FoldersGroupsBodyParams(BaseModel):
    read: bool
    write: bool
    delete: bool

    class Config:
        extra = Extra.forbid


@routes.post(
    f"/{VTAG}/folders/{{folder_id}}/groups/{{group_id}}", name="create_folder_group"
)
@login_required
@permission_required("folder.access_rights.update")
@_handle_folders_groups_exceptions
async def create_folder_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_FoldersGroupsPathParams, request)
    body_params = await parse_request_body_as(_FoldersGroupsBodyParams, request)

    folder_groups: FolderGroupGet = await _groups_api.create_folder_group_by_user(
        request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(folder_groups, web.HTTPCreated)


@routes.get(f"/{VTAG}/folders/{{folder_id}}/groups", name="list_folder_groups")
@login_required
@permission_required("folder.read")
@_handle_folders_groups_exceptions
async def list_folder_groups(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    folders: list[FolderGroupGet] = await _groups_api.list_folder_groups_by_user(
        request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(folders, web.HTTPOk)


@routes.put(
    f"/{VTAG}/folders/{{folder_id}}/groups/{{group_id}}",
    name="replace_folder_group",
)
@login_required
@permission_required("folder.access_rights.update")
@_handle_folders_groups_exceptions
async def replace_folder_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_FoldersGroupsPathParams, request)
    body_params = await parse_request_body_as(_FoldersGroupsBodyParams, request)

    return await _groups_api.update_folder_group_by_user(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        group_id=path_params.group_id,
        read=body_params.read,
        write=body_params.write,
        delete=body_params.delete,
        product_name=req_ctx.product_name,
    )


@routes.delete(
    f"/{VTAG}/folders/{{folder_id}}/groups/{{group_id}}",
    name="delete_folder_group",
)
@login_required
@permission_required("folder.access_rights.update")
@_handle_folders_groups_exceptions
async def delete_folder_group(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_FoldersGroupsPathParams, request)

    await _groups_api.delete_folder_group_by_user(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        group_id=path_params.group_id,
        product_name=req_ctx.product_name,
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
