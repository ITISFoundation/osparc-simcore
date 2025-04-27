import logging
from typing import Any

from aiohttp import web
from models_library.conversations import ConversationID, ConversationMessageID
from models_library.projects import ProjectID
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
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from ..._meta import API_VTAG as VTAG
from ...login.decorators import login_required
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response
from .. import _comments_service, _conversations_service, _projects_service
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import ProjectPathParams, RequestContext

_logger = logging.getLogger(__name__)

#
# projects/*/conversations COLLECTION -------------------------
#

routes = web.RouteTableDef()


class _ProjectConversationsPathParams(BaseModel):
    project_uuid: ProjectID
    conversation_id: ConversationID
    model_config = ConfigDict(extra="forbid")


class _ProjectConversationsMessagesPathParams(BaseModel):
    project_uuid: ProjectID
    conversation_id: ConversationID
    message_id: ConversationMessageID
    model_config = ConfigDict(extra="forbid")


class _ListProjectConversationsQueryParams(BaseModel):
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


# class _ProjectCommentsBodyParams(BaseModel):
#     contents: str
#     model_config = ConfigDict(extra="forbid")


#
### Conversations
#


@routes.post(
    f"/{VTAG}/projects/{{project_uuid}}/conversations",
    name="create_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def create_project_conversation(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    # body_params = await parse_request_body_as(_ProjectCommentsBodyParams, request)

    conversation = await _conversations_service.create_project_conversation(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_uuid,
        name=body_params.name,
        type_=body_params.type_,
    )

    return envelope_json_response({"comment_id": comment_id}, web.HTTPCreated)


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}",
    name="list_project_conversations",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def list_project_conversations(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )

    # query_params: _ListProjectCommentsQueryParams = parse_request_query_parameters_as(
    #     _ListProjectCommentsQueryParams, request
    # )

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    total_project_comments = await _comments_service.total_project_comments(
        request=request,
        project_uuid=path_params.project_uuid,
    )

    project_comments = await _comments_service.list_project_comments(
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
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}",
    name="update_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def update_project_conversation(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )
    # body_params = await parse_request_body_as(_ProjectCommentsBodyParams, request)

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    updated_comment = await _comments_service.update_project_comment(
        request=request,
        comment_id=path_params.comment_id,
        project_uuid=path_params.project_uuid,
        contents=body_params.contents,
    )
    return envelope_json_response(updated_comment)


@routes.delete(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}",
    name="delete_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def delete_project_conversation(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    await _comments_service.delete_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}",
    name="get_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_conversation(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    comment = await _comments_service.get_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
    return envelope_json_response(comment)


### Conversation Messages


@routes.post(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}/messages",
    name="create_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def create_project_conversation_message(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )
    # body_params = await parse_request_body_as(_ProjectCommentsBodyParams, request)

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    comment_id = await _comments_service.create_project_comment(
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


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}/messages",
    name="list_project_conversation_messages",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def list_project_conversation_messages(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ProjectCommentsPathParams, request)
    query_params: _ListProjectCommentsQueryParams = parse_request_query_parameters_as(
        _ListProjectCommentsQueryParams, request
    )

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    total_project_comments = await _comments_service.total_project_comments(
        request=request,
        project_uuid=path_params.project_uuid,
    )

    project_comments = await _comments_service.list_project_comments(
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
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="update_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def update_project_conversation_message(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsMessagesPathParams, request
    )
    body_params = await parse_request_body_as(_ProjectCommentsBodyParams, request)

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    updated_comment = await _comments_service.update_project_comment(
        request=request,
        comment_id=path_params.comment_id,
        project_uuid=path_params.project_uuid,
        contents=body_params.contents,
    )
    return envelope_json_response(updated_comment)


@routes.delete(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="delete_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def delete_project_conversation_message(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsMessagesPathParams, request
    )

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    await _comments_service.delete_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="get_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_conversation_message(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsMessagesPathParams, request
    )

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_uuid}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    comment = await _comments_service.get_project_comment(
        request=request,
        comment_id=path_params.comment_id,
    )
    return envelope_json_response(comment)
