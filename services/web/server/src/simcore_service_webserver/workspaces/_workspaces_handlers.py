import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.workspaces import (
    CreateWorkspaceBodyParams,
    PutWorkspaceBodyParams,
    WorkspaceGet,
    WorkspaceGetPage,
)
from models_library.basic_types import IDStr
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from pydantic import Extra, Field, Json, parse_obj_as, validator
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _workspaces_api
from .errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError

_logger = logging.getLogger(__name__)


def handle_workspaces_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WorkspaceNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except WorkspaceAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# workspaces COLLECTION -------------------------
#

routes = web.RouteTableDef()


class WorkspacesRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class WorkspacesPathParams(StrictRequestParameters):
    workspace_id: WorkspaceID


class WorkspacesListWithJsonStrQueryParams(PageQueryParameters):
    # pylint: disable=unsubscriptable-object
    order_by: Json[OrderBy] = Field(
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        description="Order by field (modified_at|name|description) and direction (asc|desc). The default sorting order is ascending.",
        example='{"field": "name", "direction": "desc"}',
        alias="order_by",
    )

    @validator("order_by", check_fields=False)
    @classmethod
    def validate_order_by_field(cls, v):
        if v.field not in {
            "modified_at",
            "name",
            "description",
        }:
            msg = f"We do not support ordering by provided field {v.field}"
            raise ValueError(msg)
        if v.field == "modified_at":
            v.field = "modified"
        return v

    class Config:
        extra = Extra.forbid


@routes.post(f"/{VTAG}/workspaces", name="create_workspace")
@login_required
@permission_required("workspaces.*")
@handle_workspaces_exceptions
async def create_workspace(request: web.Request):
    req_ctx = WorkspacesRequestContext.parse_obj(request)
    body_params = await parse_request_body_as(CreateWorkspaceBodyParams, request)

    workspace: WorkspaceGet = await _workspaces_api.create_workspace(
        request.app,
        user_id=req_ctx.user_id,
        name=body_params.name,
        description=body_params.description,
        thumbnail=body_params.thumbnail,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(workspace, web.HTTPCreated)


@routes.get(f"/{VTAG}/workspaces", name="list_workspaces")
@login_required
@permission_required("workspaces.*")
@handle_workspaces_exceptions
async def list_workspaces(request: web.Request):
    req_ctx = WorkspacesRequestContext.parse_obj(request)
    query_params: WorkspacesListWithJsonStrQueryParams = (
        parse_request_query_parameters_as(WorkspacesListWithJsonStrQueryParams, request)
    )

    workspaces: WorkspaceGetPage = await _workspaces_api.list_workspaces(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=parse_obj_as(OrderBy, query_params.order_by),
    )

    page = Page[WorkspaceGet].parse_obj(
        paginate_data(
            chunk=workspaces.items,
            request_url=request.url,
            total=workspaces.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(f"/{VTAG}/workspaces/{{workspace_id}}", name="get_workspace")
@login_required
@permission_required("workspaces.*")
@handle_workspaces_exceptions
async def get_workspace(request: web.Request):
    req_ctx = WorkspacesRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)

    workspace: WorkspaceGet = await _workspaces_api.get_workspace(
        app=request.app,
        workspace_id=path_params.workspace_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(workspace)


@routes.put(
    f"/{VTAG}/workspaces/{{workspace_id}}",
    name="replace_workspace",
)
@login_required
@permission_required("workspaces.*")
@handle_workspaces_exceptions
async def replace_workspace(request: web.Request):
    req_ctx = WorkspacesRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)
    body_params = await parse_request_body_as(PutWorkspaceBodyParams, request)

    workspace: WorkspaceGet = await _workspaces_api.update_workspace(
        app=request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        name=body_params.name,
        description=body_params.description,
        product_name=req_ctx.product_name,
        thumbnail=body_params.thumbnail,
    )
    return envelope_json_response(workspace)


@routes.delete(
    f"/{VTAG}/workspaces/{{workspace_id}}",
    name="delete_workspace",
)
@login_required
@permission_required("workspaces.*")
@handle_workspaces_exceptions
async def delete_workspace(request: web.Request):
    req_ctx = WorkspacesRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(WorkspacesPathParams, request)

    await _workspaces_api.delete_workspace(
        app=request.app,
        user_id=req_ctx.user_id,
        workspace_id=path_params.workspace_id,
        product_name=req_ctx.product_name,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
