""" Handlers for project comments operations

"""

import functools
import logging
from typing import Any

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_comments import CommentID
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from models_library.rest_pagination_utils import paginate_data
from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _comments_api, projects_api
from ._common_models import RequestContext
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


def _handle_project_comments_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc
        except ProjectInvalidRightsError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


#
# projects/*/comments COLLECTION -------------------------
#

routes = web.RouteTableDef()


class _ProjectCommentsPathParams(BaseModel):
    project_uuid: ProjectID
    model_config = ConfigDict(extra="forbid")


class _ProjectCommentsWithCommentPathParams(BaseModel):
    project_uuid: ProjectID
    comment_id: CommentID
    model_config = ConfigDict(extra="forbid")


class _ProjectCommentsBodyParams(BaseModel):
    contents: str
    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{VTAG}/projects/{{project_uuid}}/comments", name="create_project_comment"
)
@login_required
@permission_required("project.read")
@_handle_project_comments_exceptions
async def create_project_comment(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectCommentsPathParams, request)
    body_params = await parse_request_body_as(_ProjectCommentsBodyParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    comment_id = await _comments_api.create_project_comment(
        request=request,
        project_uuid=path_params.project_uuid,
        user_id=req_ctx.user_id,
        contents=body_params.contents,
    )

    return envelope_json_response({"comment_id": comment_id}, web.HTTPCreated)


class _ListProjectCommentsQueryParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )
    model_config = ConfigDict(extra="forbid")


@routes.get(f"/{VTAG}/projects/{{project_uuid}}/comments", name="list_project_comments")
@login_required
@permission_required("project.read")
@_handle_project_comments_exceptions
async def list_project_comments(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectCommentsPathParams, request)
    query_params: _ListProjectCommentsQueryParams = parse_request_query_parameters_as(
        _ListProjectCommentsQueryParams, request
    )

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    total_project_comments = await _comments_api.total_project_comments(
        request=request,
        project_uuid=path_params.project_uuid,
    )

    project_comments = await _comments_api.list_project_comments(
        request=request,
        project_uuid=path_params.project_uuid,
        offset=query_params.offset,
        limit=query_params.limit,
    )

    page = Page[dict[str, Any]].model_validate(
        paginate_data(
            chunk=project_comments,
            request_url=request.url,
            total=total_project_comments,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.put(
    f"/{VTAG}/projects/{{project_uuid}}/comments/{{comment_id}}",
    name="update_project_comment",
)
@login_required
@permission_required("project.read")
async def update_project_comment(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectCommentsWithCommentPathParams, request
    )
    body_params = await parse_request_body_as(_ProjectCommentsBodyParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    return await _comments_api.update_project_comment(
        request=request,
        comment_id=path_params.comment_id,
        project_uuid=path_params.project_uuid,
        contents=body_params.contents,
    )


@routes.delete(
    f"/{VTAG}/projects/{{project_uuid}}/comments/{{comment_id}}",
    name="delete_project_comment",
)
@login_required
@permission_required("project.read")
@_handle_project_comments_exceptions
async def delete_project_comment(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectCommentsWithCommentPathParams, request
    )

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    await _comments_api.delete_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/comments/{{comment_id}}",
    name="get_project_comment",
)
@login_required
@permission_required("project.read")
@_handle_project_comments_exceptions
async def get_project_comment(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectCommentsWithCommentPathParams, request
    )

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    return await _comments_api.get_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
