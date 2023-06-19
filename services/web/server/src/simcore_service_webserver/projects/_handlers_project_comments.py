""" Handlers for project comments operations

"""

import logging
from typing import Any

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_comments import CommentID
from models_library.rest_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, Page
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field, NonNegativeInt
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import projects_api
from ._handlers_crud import RequestContext

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class _CreateProjectCommentsPathParams(BaseModel):
    project_uuid: ProjectID

    class Config:
        extra = Extra.forbid


class _CreateProjectCommentsBodyParams(BaseModel):
    content: str
    user_id: UserID

    class Config:
        extra = Extra.forbid


@routes.post(
    f"/{VTAG}/projects/{{project_uuid}}/comments", name="create_project_comment"
)
@login_required
@permission_required("project.open")
async def create_project_comment(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(
        _CreateProjectCommentsPathParams, request
    )
    body_params = await parse_request_body_as(_CreateProjectCommentsBodyParams, request)

    if req_ctx.user_id != body_params.user_id:
        raise web.HTTPForbidden(
            reason="User id in body does not match with the logged in user id"
        )

    comment_id = await projects_api.create_project_comment(
        request=request,
        project_uuid=path_params.project_uuid,
        user_id=req_ctx.user_id,
        content=body_params.content,
    )

    return web.json_response(
        {"data": comment_id}, status=web.HTTPCreated.status_code, dumps=json_dumps
    )


class _ListProjectCommentsPathParams(BaseModel):
    project_uuid: ProjectID

    class Config:
        extra = Extra.forbid


class _ListProjectCommentsQueryParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=50,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )

    class Config:
        extra = Extra.forbid


@routes.get(f"/{VTAG}/projects/{{project_uuid}}/comments", name="list_project_comments")
@login_required
@permission_required("project.open")
async def list_project_comments(request: web.Request):
    path_params = parse_request_path_parameters_as(
        _ListProjectCommentsPathParams, request
    )
    query_params = parse_request_query_parameters_as(
        _ListProjectCommentsQueryParams, request
    )

    total_project_comments = await projects_api.total_project_comments(
        request=request,
        project_uuid=path_params.project_uuid,
    )

    project_comments = await projects_api.list_project_comments(
        request=request,
        project_uuid=path_params.project_uuid,
        offset=query_params.offset,
        limit=query_params.limit,
    )

    page = Page[dict[str, Any]].parse_obj(
        paginate_data(
            chunk=project_comments,
            request_url=request.url,
            total=total_project_comments,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


class _UpdateProjectCommentsPathParams(BaseModel):
    project_uuid: ProjectID
    comment_id: CommentID

    class Config:
        extra = Extra.forbid


class _UpdateProjectCommentsBodyParams(BaseModel):
    content: str
    user_id: UserID

    class Config:
        extra = Extra.forbid


@routes.put(
    f"/{VTAG}/projects/{{project_uuid}}/comments/{{comment_id}}",
    name="update_project_comment",
)
@login_required
@permission_required("project.open")
async def update_project_comment(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(
        _UpdateProjectCommentsPathParams, request
    )
    body_params = await parse_request_body_as(_UpdateProjectCommentsBodyParams, request)

    return await projects_api.update_project_comment(
        request=request,
        comment_id=path_params.comment_id,
        project_uuid=path_params.project_uuid,
        user_id=req_ctx.user_id,
        content=body_params.content,
    )


class _DeleteProjectCommentsPathParams(BaseModel):
    project_uuid: ProjectID
    comment_id: CommentID

    class Config:
        extra = Extra.forbid


@routes.delete(
    f"/{VTAG}/projects/{{project_uuid}}/comments/{{comment_id}}",
    name="delete_project_comment",
)
@login_required
@permission_required("project.open")
async def delete_project_comment(request: web.Request):
    path_params = parse_request_path_parameters_as(
        _DeleteProjectCommentsPathParams, request
    )

    await projects_api.delete_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


class _GetProjectsCommentPathParams(BaseModel):
    project_uuid: ProjectID
    comment_id: CommentID

    class Config:
        extra = Extra.forbid


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/comments/{{comment_id}}",
    name="get_project_comment",
)
@login_required
@permission_required("project.open")
async def get_project_comment(request: web.Request):
    path_params = parse_request_path_parameters_as(
        _GetProjectsCommentPathParams, request
    )

    return await projects_api.get_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
