import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.folders import (
    CreateFolderBodyParams,
    FolderGet,
    PutFolderBodyParams,
)
from models_library.folders import FolderID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageQueryParameters
from models_library.users import UserID
from pydantic import Extra, Field, Json, parse_obj_as, validator
from servicelib.aiohttp.requests_validation import (
    RequestParams,
    StrictRequestParams,
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..application_settings_utils import requires_dev_feature_enabled
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _folders_api
from .errors import FolderAccessForbiddenError, FolderNotFoundError

_logger = logging.getLogger(__name__)


def handle_folders_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except FolderNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except FolderAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# folders COLLECTION -------------------------
#

routes = web.RouteTableDef()


class FoldersRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


class FoldersPathParams(StrictRequestParams):
    folder_id: FolderID


class FolderListParams(PageQueryParameters):
    ...


class FolderListWithJsonStrParams(FolderListParams):
    order_by: Json[OrderBy] = Field(  # pylint: disable=unsubscriptable-object
        default=OrderBy(field="name", direction=OrderDirection.DESC),
        description="Order by field (name|description) and direction (asc|desc). The default sorting order is ascending.",
        example='{"field": "name", "direction": "desc"}',
        alias="order_by",
    )

    @validator("order_by", check_fields=False)
    @classmethod
    def validate_order_by_field(cls, v):
        if v.field not in {
            "name",
            "description",
        }:
            raise ValueError(f"We do not support ordering by provided field {v.field}")
        return v

    class Config:
        extra = Extra.forbid


@routes.post(f"/{VTAG}/folders", name="create_folder")
@requires_dev_feature_enabled
@login_required
@permission_required("folder.create")
@handle_folders_exceptions
async def create_folder(request: web.Request):
    req_ctx = FoldersRequestContext.parse_obj(request)
    body_params = await parse_request_body_as(CreateFolderBodyParams, request)

    folder: FolderGet = await _folders_api.create_folder_by_user(
        request.app,
        user_id=req_ctx.user_id,
        folder_name=body_params.name,
        description=body_params.description,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(folder, web.HTTPCreated)


@routes.get(f"/{VTAG}/folders", name="list_folders")
@login_required
@permission_required("folder.read")
@handle_folders_exceptions
async def list_folders(request: web.Request):
    req_ctx = FoldersRequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(
        FolderListWithJsonStrParams, request
    )

    folders: list[FolderGet] = await _folders_api.list_folders_by_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=parse_obj_as(OrderBy, query_params.order_by),
    )

    return envelope_json_response(folders)


@routes.get(f"/{VTAG}/folders/{{folder_id}}", name="get_folder")
@login_required
@permission_required("folder.read")
@handle_folders_exceptions
async def get_folder(request: web.Request):
    req_ctx = FoldersRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    folder: FolderGet = await _folders_api.get_folder_by_user(
        app=request.app,
        folder_id=path_params.folder_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(folder)


@routes.put(
    f"/{VTAG}/folders/{{folder_id}}",
    name="replace_folder",
)
@login_required
@permission_required("folder.update")
@handle_folders_exceptions
async def replace_folder(request: web.Request):
    req_ctx = FoldersRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)
    body_params = await parse_request_body_as(PutFolderBodyParams, request)

    updated_folder: FolderGet = await _folders_api.update_folder_by_user(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        name=body_params.name,
        description=body_params.description,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(updated_folder)


@routes.delete(
    f"/{VTAG}/folders/{{folder_id}}",
    name="delete_folder",
)
@login_required
@permission_required("folder.delete")
@handle_folders_exceptions
async def delete_folder_group(request: web.Request):
    req_ctx = FoldersRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(FoldersPathParams, request)

    await _folders_api.delete_folder_by_user(
        app=request.app,
        user_id=req_ctx.user_id,
        folder_id=path_params.folder_id,
        product_name=req_ctx.product_name,
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
