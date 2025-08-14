import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver._base import InputSchema
from models_library.api_schemas_webserver.conversations import (
    ConversationMessagePatch,
    ConversationMessageRestGet,
    ConversationPatch,
    ConversationRestGet,
)
from models_library.conversations import (
    ConversationID,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationPatchDB,
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
from ...utils_aiohttp import envelope_json_response
from .. import conversations_service
from .._conversation_service import (
    get_support_conversation_for_user,
    list_support_conversations_for_user,
)

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


#
# conversations COLLECTION -------------------------
#


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


class _ConversationsCreateBodyParams(InputSchema):
    name: str
    type: ConversationType
    extra_context: dict[str, Any] | None = None


class _ConversationsPutBodyParams(InputSchema):
    name: str


def _raise_bad_request(reason: str):
    raise web.HTTPBadRequest(reason=reason)


@routes.post(
    f"/{VTAG}/conversations",
    name="create_conversation",
)
@login_required
async def create_conversation(request: web.Request):
    """Create a new conversation (supports only type='support')"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        body_params = await parse_request_body_as(
            _ConversationsCreateBodyParams, request
        )

        # Ensure only support conversations are allowed
        if body_params.type != ConversationType.SUPPORT:
            _raise_bad_request("Only support conversations are allowed")

        _extra_context = body_params.extra_context or {}

        conversation = await conversations_service.create_conversation(
            app=request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            project_uuid=None,  # Support conversations are not tied to projects
            name=body_params.name,
            type_=body_params.type,
            extra_context=_extra_context,
        )
        data = ConversationRestGet.from_domain_model(conversation)

        return envelope_json_response(data, web.HTTPCreated)

    except web.HTTPError:
        raise
    except Exception as exc:
        _logger.exception("Failed to create conversation")
        raise web.HTTPInternalServerError(
            reason="Failed to create conversation"
        ) from exc


@routes.get(
    f"/{VTAG}/conversations",
    name="list_conversations",
)
@login_required
async def list_conversations(request: web.Request):
    """List conversations for the authenticated user (supports only type='support')"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        query_params = parse_request_query_parameters_as(
            _ListConversationsQueryParams, request
        )

        total, conversations = await list_support_conversations_for_user(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            offset=query_params.offset,
            limit=query_params.limit,
        )

        page = Page[ConversationRestGet].model_validate(
            paginate_data(
                chunk=[
                    ConversationRestGet.from_domain_model(conversation)
                    for conversation in conversations
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

    except Exception as exc:
        _logger.exception("Failed to list conversations")
        raise web.HTTPInternalServerError(
            reason="Failed to list conversations"
        ) from exc


@routes.get(
    f"/{VTAG}/conversations/{{conversation_id}}",
    name="get_conversation",
)
@login_required
async def get_conversation(request: web.Request):
    """Get a specific conversation"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
        query_params = parse_request_query_parameters_as(
            _GetConversationsQueryParams, request
        )
        assert query_params.type == ConversationType.SUPPORT  # nosec

        conversation = await get_support_conversation_for_user(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            conversation_id=path_params.conversation_id,
        )

        data = ConversationRestGet.from_domain_model(conversation)
        return envelope_json_response(data)

    except Exception as exc:
        _logger.exception("Failed to get conversation")
        raise web.HTTPNotFound(reason="Conversation not found") from exc


@routes.put(
    f"/{VTAG}/conversations/{{conversation_id}}",
    name="update_conversation",
)
@login_required
async def update_conversation(request: web.Request):
    """Update a conversation"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
        body_params = await parse_request_body_as(ConversationPatch, request)
        query_params = parse_request_query_parameters_as(
            _GetConversationsQueryParams, request
        )

        assert query_params.type == ConversationType.SUPPORT  # nosec

        await get_support_conversation_for_user(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            conversation_id=path_params.conversation_id,
        )

        conversation = await conversations_service.update_conversation(
            app=request.app,
            project_id=None,  # Support conversations don't use project_id
            conversation_id=path_params.conversation_id,
            updates=ConversationPatchDB(name=body_params.name),
        )

        data = ConversationRestGet.from_domain_model(conversation)
        return envelope_json_response(data)

    except Exception as exc:
        _logger.exception("Failed to update conversation")
        raise web.HTTPNotFound(reason="Conversation not found") from exc


@routes.delete(
    f"/{VTAG}/conversations/{{conversation_id}}",
    name="delete_conversation",
)
@login_required
async def delete_conversation(request: web.Request):
    """Delete a conversation"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
        query_params = parse_request_query_parameters_as(
            _GetConversationsQueryParams, request
        )
        assert query_params.type == ConversationType.SUPPORT  # nosec

        await get_support_conversation_for_user(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            conversation_id=path_params.conversation_id,
        )

        await conversations_service.delete_conversation(
            app=request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            project_id=None,  # Support conversations don't use project_id
            conversation_id=path_params.conversation_id,
        )

        return web.json_response(status=status.HTTP_204_NO_CONTENT)

    except Exception as exc:
        _logger.exception("Failed to delete conversation")
        raise web.HTTPNotFound(reason="Conversation not found") from exc


#
# conversations/*/messages COLLECTION -------------------------
#


@routes.post(
    f"/{VTAG}/conversations/{{conversation_id}}/messages",
    name="create_conversation_message",
)
@login_required
async def create_conversation_message(request: web.Request):
    """Create a new message in a conversation"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
        body_params = await parse_request_body_as(ConversationMessageCreate, request)

        # For support conversations, we need a dummy project_id since the service requires it
        from uuid import uuid4

        dummy_project_id = uuid4()  # This won't be used for support conversations

        message = await conversations_service.create_message(
            app=request.app,
            user_id=req_ctx.user_id,
            project_id=dummy_project_id,  # Support conversations don't use project_id
            conversation_id=path_params.conversation_id,
            content=body_params.content,
            type_=body_params.type,
        )

        data = ConversationMessageRestGet.from_domain_model(message)
        return envelope_json_response(data, web.HTTPCreated)

    except Exception as exc:
        _logger.exception("Failed to create conversation message")
        raise web.HTTPInternalServerError(
            reason="Failed to create conversation message"
        ) from exc


@routes.get(
    f"/{VTAG}/conversations/{{conversation_id}}/messages",
    name="list_conversation_messages",
)
@login_required
async def list_conversation_messages(request: web.Request):
    """List messages in a conversation"""
    try:
        path_params = parse_request_path_parameters_as(_ConversationPathParams, request)
        query_params = parse_request_query_parameters_as(
            _ListConversationsQueryParams, request
        )

        total, messages = await conversations_service.list_messages_for_conversation(
            app=request.app,
            conversation_id=path_params.conversation_id,
            offset=query_params.offset,
            limit=query_params.limit,
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

    except Exception as exc:
        _logger.exception("Failed to list conversation messages")
        raise web.HTTPInternalServerError(
            reason="Failed to list conversation messages"
        ) from exc


@routes.get(
    f"/{VTAG}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="get_conversation_message",
)
@login_required
async def get_conversation_message(request: web.Request):
    """Get a specific message in a conversation"""
    try:
        path_params = parse_request_path_parameters_as(
            _ConversationMessagePathParams, request
        )

        message = await conversations_service.get_message(
            app=request.app,
            conversation_id=path_params.conversation_id,
            message_id=path_params.message_id,
        )

        data = ConversationMessageRestGet.from_domain_model(message)
        return envelope_json_response(data)

    except Exception as exc:
        _logger.exception("Failed to get conversation message")
        raise web.HTTPNotFound(reason="Message not found") from exc


@routes.put(
    f"/{VTAG}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="update_conversation_message",
)
@login_required
async def update_conversation_message(request: web.Request):
    """Update a message in a conversation"""
    try:
        path_params = parse_request_path_parameters_as(
            _ConversationMessagePathParams, request
        )
        body_params = await parse_request_body_as(ConversationMessagePatch, request)

        message = await conversations_service.update_message(
            app=request.app,
            project_id=None,  # Support conversations don't use project_id
            conversation_id=path_params.conversation_id,
            message_id=path_params.message_id,
            updates=ConversationMessagePatchDB(content=body_params.content),
        )

        data = ConversationMessageRestGet.from_domain_model(message)
        return envelope_json_response(data)

    except Exception as exc:
        _logger.exception("Failed to update conversation message")
        raise web.HTTPNotFound(reason="Message not found") from exc


@routes.delete(
    f"/{VTAG}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="delete_conversation_message",
)
@login_required
async def delete_conversation_message(request: web.Request):
    """Delete a message in a conversation"""
    try:
        req_ctx = AuthenticatedRequestContext.model_validate(request)
        path_params = parse_request_path_parameters_as(
            _ConversationMessagePathParams, request
        )

        await conversations_service.delete_message(
            app=request.app,
            user_id=req_ctx.user_id,
            project_id=None,  # Support conversations don't use project_id
            conversation_id=path_params.conversation_id,
            message_id=path_params.message_id,
        )

        return web.json_response(status=status.HTTP_204_NO_CONTENT)

    except Exception as exc:
        _logger.exception("Failed to delete conversation message")
        raise web.HTTPNotFound(reason="Message not found") from exc
