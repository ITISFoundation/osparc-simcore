import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver._base import InputSchema
from models_library.api_schemas_webserver.conversations import (
    ConversationPatch,
    ConversationRestGet,
)
from models_library.conversations import (
    ConversationPatchDB,
    ConversationType,
)
from models_library.rest_pagination import (
    Page,
    PageQueryParameters,
)
from models_library.rest_pagination_utils import paginate_data
from pydantic import ConfigDict, field_validator
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
from .. import _conversation_service, conversations_service
from ._common import ConversationPathParams, raise_unsupported_type
from ._rest_exceptions import _handle_exceptions

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class _ListConversationsQueryParams(PageQueryParameters):
    type: ConversationType
    model_config = ConfigDict(extra="forbid")

    @field_validator("type")
    @classmethod
    def validate_type(cls, value):
        if value is not None and value.is_support_type() is False:
            msg = "Only support type conversations are allowed"
            raise ValueError(msg)
        return value


class _ConversationsCreateBodyParams(InputSchema):
    name: str
    type: ConversationType
    extra_context: dict[str, Any] | None = None


@routes.post(
    f"/{VTAG}/conversations",
    name="create_conversation",
)
@login_required
@_handle_exceptions
async def create_conversation(request: web.Request):
    """Create a new conversation (supports only type='support')"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body_params = await parse_request_body_as(_ConversationsCreateBodyParams, request)
    # Ensure only support conversations are allowed
    if body_params.type.is_support_type() is False:
        raise_unsupported_type(body_params.type)

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


@routes.get(
    f"/{VTAG}/conversations",
    name="list_conversations",
)
@login_required
@_handle_exceptions
async def list_conversations(request: web.Request):
    """List conversations for the authenticated user (supports only type='support')"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    query_params = parse_request_query_parameters_as(
        _ListConversationsQueryParams, request
    )
    if query_params.type.is_support_type() is False:
        raise_unsupported_type(query_params.type)

    total, conversations = (
        await _conversation_service.list_support_conversations_for_user(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            offset=query_params.offset,
            limit=query_params.limit,
        )
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


@routes.get(
    f"/{VTAG}/conversations/{{conversation_id}}",
    name="get_conversation",
)
@login_required
@_handle_exceptions
async def get_conversation(request: web.Request):
    """Get a specific conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ConversationPathParams, request)

    conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if conversation.type.is_support_type() is False:
        raise_unsupported_type(conversation.type)

    conversation, _ = await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

    data = ConversationRestGet.from_domain_model(conversation)
    return envelope_json_response(data)


@routes.patch(
    f"/{VTAG}/conversations/{{conversation_id}}",
    name="update_conversation",
)
@login_required
@_handle_exceptions
async def update_conversation(request: web.Request):
    """Update a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ConversationPathParams, request)
    body_params = await parse_request_body_as(ConversationPatch, request)

    conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if conversation.type.is_support_type() is False:
        raise_unsupported_type(conversation.type)

    await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

    conversation = await conversations_service.update_conversation(
        app=request.app,
        project_id=None,  # Support conversations don't use project_id
        conversation_id=path_params.conversation_id,
        updates=ConversationPatchDB(**body_params.model_dump(exclude_unset=True)),
    )

    data = ConversationRestGet.from_domain_model(conversation)
    return envelope_json_response(data)


@routes.delete(
    f"/{VTAG}/conversations/{{conversation_id}}",
    name="delete_conversation",
)
@login_required
@_handle_exceptions
async def delete_conversation(request: web.Request):
    """Delete a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ConversationPathParams, request)

    conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if conversation.type.is_support_type() is False:
        raise_unsupported_type(conversation.type)

    # Only support conversation creator can delete conversation
    _user_group_id = await users_service.get_user_primary_group_id(
        request.app, user_id=req_ctx.user_id
    )
    await _conversation_service.get_conversation_for_user(
        app=request.app,
        conversation_id=path_params.conversation_id,
        user_group_id=_user_group_id,
    )

    await conversations_service.delete_conversation(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=None,  # Support conversations don't use project_id
        conversation_id=path_params.conversation_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
