import logging

from aiohttp import web
from models_library.api_schemas_webserver.conversations import (
    ConversationMessagePatch,
    ConversationMessageRestGet,
)
from models_library.conversations import (
    ConversationID,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
    ConversationType,
)
from models_library.rest_pagination import (
    Page,
    PageQueryParameters,
)
from models_library.rest_pagination_utils import paginate_data
from pydantic import BaseModel, ConfigDict, field_validator
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
from ...models import AuthenticatedRequestContext
from ...users import users_service
from ...utils_aiohttp import envelope_json_response
from .. import _conversation_message_service, _conversation_service
from ._common import raise_unsupported_type
from ._rest_exceptions import _handle_exceptions

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class _ConversationPathParams(BaseModel):
    conversation_id: ConversationID
    model_config = ConfigDict(extra="forbid")


class _ConversationMessagePathParams(_ConversationPathParams):
    message_id: ConversationMessageID
    model_config = ConfigDict(extra="forbid")


class _GetConversationsQueryParams(BaseModel):
    type: ConversationType
    model_config = ConfigDict(extra="forbid")

    @field_validator("type")
    @classmethod
    def validate_type(cls, value):
        if value is not None and value != ConversationType.SUPPORT:
            raise ValueError("Only support conversations are allowed")
        return value


class _ListConversationsQueryParams(PageQueryParameters, _GetConversationsQueryParams):

    model_config = ConfigDict(extra="forbid")


class _ConversationMessageCreateBodyParams(BaseModel):
    content: str
    type: ConversationMessageType
    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{VTAG}/conversations/{{conversation_id}}/messages",
    name="create_conversation_message",
)
@login_required
@_handle_exceptions
async def create_conversation_message(request: web.Request):
    """Create a new message in a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
    body_params = await parse_request_body_as(
        _ConversationMessageCreateBodyParams, request
    )

    user_primary_gid = await users_service.get_user_primary_group_id(
        request.app, user_id=req_ctx.user_id
    )
    conversation = await _conversation_service.get_conversation_for_user(
        app=request.app,
        conversation_id=path_params.conversation_id,
        user_group_id=user_primary_gid,
    )
    # Ensure only support conversations are allowed
    if conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(conversation.type)

    message = await _conversation_message_service.create_message(
        app=request.app,
        user_id=req_ctx.user_id,
        project_id=None,  # Support conversations don't use project_id
        conversation_id=path_params.conversation_id,
        content=body_params.content,
        type_=body_params.type,
    )

    data = ConversationMessageRestGet.from_domain_model(message)
    return envelope_json_response(data, web.HTTPCreated)


@routes.get(
    f"/{VTAG}/conversations/{{conversation_id}}/messages",
    name="list_conversation_messages",
)
@login_required
@_handle_exceptions
async def list_conversation_messages(request: web.Request):
    """List messages in a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
    query_params = parse_request_query_parameters_as(
        _ListConversationsQueryParams, request
    )

    user_primary_gid = await users_service.get_user_primary_group_id(
        request.app, user_id=req_ctx.user_id
    )
    conversation = await _conversation_service.get_conversation_for_user(
        app=request.app,
        conversation_id=path_params.conversation_id,
        user_group_id=user_primary_gid,
    )
    if conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(conversation.type)

    total, messages = (
        await _conversation_message_service.list_messages_for_conversation(
            app=request.app,
            conversation_id=path_params.conversation_id,
            offset=query_params.offset,
            limit=query_params.limit,
        )
    )

    page = Page[ConversationMessageRestGet].model_validate(
        paginate_data(
            chunk=[
                ConversationMessageRestGet.from_domain_model(message)
                for message in messages
            ],
            request_url=request.url,
            total=total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(
    f"/{VTAG}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="get_conversation_message",
)
@login_required
@_handle_exceptions
async def get_conversation_message(request: web.Request):
    """Get a specific message in a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ConversationMessagePathParams, request
    )

    user_primary_gid = await users_service.get_user_primary_group_id(
        request.app, user_id=req_ctx.user_id
    )
    conversation = await _conversation_service.get_conversation_for_user(
        app=request.app,
        conversation_id=path_params.conversation_id,
        user_group_id=user_primary_gid,
    )
    if conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(conversation.type)

    message = await _conversation_message_service.get_message(
        app=request.app,
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
    )

    data = ConversationMessageRestGet.from_domain_model(message)
    return envelope_json_response(data)


@routes.put(
    f"/{VTAG}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="update_conversation_message",
)
@login_required
@_handle_exceptions
async def update_conversation_message(request: web.Request):
    """Update a message in a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ConversationMessagePathParams, request
    )
    body_params = await parse_request_body_as(ConversationMessagePatch, request)

    user_primary_gid = await users_service.get_user_primary_group_id(
        request.app, user_id=req_ctx.user_id
    )
    conversation = await _conversation_service.get_conversation_for_user(
        app=request.app,
        conversation_id=path_params.conversation_id,
        user_group_id=user_primary_gid,
    )
    if conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(conversation.type)

    message = await _conversation_message_service.update_message(
        app=request.app,
        project_id=None,  # Support conversations don't use project_id
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
        updates=ConversationMessagePatchDB(content=body_params.content),
    )

    data = ConversationMessageRestGet.from_domain_model(message)
    return envelope_json_response(data)


@routes.delete(
    f"/{VTAG}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="delete_conversation_message",
)
@login_required
@_handle_exceptions
async def delete_conversation_message(request: web.Request):
    """Delete a message in a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ConversationMessagePathParams, request
    )

    user_primary_gid = await users_service.get_user_primary_group_id(
        request.app, user_id=req_ctx.user_id
    )
    conversation = await _conversation_service.get_conversation_for_user(
        app=request.app,
        conversation_id=path_params.conversation_id,
        user_group_id=user_primary_gid,
    )
    if conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(conversation.type)

    await _conversation_message_service.delete_message(
        app=request.app,
        user_id=req_ctx.user_id,
        project_id=None,  # Support conversations don't use project_id
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
