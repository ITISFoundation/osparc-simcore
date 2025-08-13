import logging

from aiohttp import web
from models_library.api_schemas_webserver._base import InputSchema
from models_library.api_schemas_webserver.conversations import (
    ConversationMessageRestGet,
    ConversationRestGet,
)
from models_library.conversations import (
    ConversationID,
    ConversationMessageID,
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
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response
from .. import _conversations_service
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext, ProjectPathParams

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


#
# projects/*/conversations COLLECTION -------------------------
#


class _ProjectConversationsPathParams(ProjectPathParams):
    conversation_id: ConversationID


class _ListProjectConversationsQueryParams(PageQueryParameters): ...


class _ProjectConversationsCreateBodyParams(InputSchema):
    name: str
    type: ConversationType

    @field_validator("type")
    @classmethod
    def validate_type(cls, value):
        if value is not None and value not in [
            ConversationType.PROJECT_ANNOTATION,
            ConversationType.PROJECT_STATIC,
        ]:
            raise ValueError("Only project conversations are allowed")
        return value


class _ProjectConversationsPutBodyParams(InputSchema):
    name: str


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/conversations",
    name="create_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def create_project_conversation(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    body_params = await parse_request_body_as(
        _ProjectConversationsCreateBodyParams, request
    )
    _extra_context = (
        body_params.extra_context if body_params.extra_context is not None else {}
    )

    conversation = await _conversations_service.create_project_conversation(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        name=body_params.name,
        conversation_type=body_params.type,
        extra_context=_extra_context,
    )
    data = ConversationRestGet.from_domain_model(conversation)

    return envelope_json_response(data, web.HTTPCreated)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/conversations",
    name="list_project_conversations",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def list_project_conversations(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params = parse_request_query_parameters_as(
        _ListProjectConversationsQueryParams, request
    )

    total, conversations = await _conversations_service.list_project_conversations(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
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


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}",
    name="update_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def update_project_conversation(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )
    body_params = await parse_request_body_as(
        _ProjectConversationsPutBodyParams, request
    )

    conversation = await _conversations_service.update_project_conversation(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
        name=body_params.name,
    )
    data = ConversationRestGet.from_domain_model(conversation)

    return envelope_json_response(data)


@routes.delete(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}",
    name="delete_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def delete_project_conversation(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )

    await _conversations_service.delete_project_conversation(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}",
    name="get_project_conversation",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_conversation(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )

    conversation = await _conversations_service.get_project_conversation(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
    )
    data = ConversationRestGet.from_domain_model(conversation)

    return envelope_json_response(data)


#
# projects/*/conversations/*/messages COLLECTION -------------------------
#


class _ProjectConversationsMessagesPathParams(_ProjectConversationsPathParams):
    message_id: ConversationMessageID
    model_config = ConfigDict(extra="forbid")


class _ListProjectConversationMessagesQueryParams(PageQueryParameters):
    model_config = ConfigDict(extra="forbid")


class _ProjectConversationMessagesCreateBodyParams(BaseModel):
    content: str
    type: ConversationMessageType
    model_config = ConfigDict(extra="forbid")


class _ProjectConversationMessagesPutBodyParams(BaseModel):
    content: str
    model_config = ConfigDict(extra="forbid")


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}/messages",
    name="create_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def create_project_conversation_message(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )
    body_params = await parse_request_body_as(
        _ProjectConversationMessagesCreateBodyParams, request
    )

    message = await _conversations_service.create_project_conversation_message(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
        content=body_params.content,
        message_type=body_params.type,
    )
    data = ConversationMessageRestGet.from_domain_model(message)

    return envelope_json_response(data, web.HTTPCreated)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}/messages",
    name="list_project_conversation_messages",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def list_project_conversation_messages(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsPathParams, request
    )
    query_params: _ListProjectConversationMessagesQueryParams = (
        parse_request_query_parameters_as(
            _ListProjectConversationMessagesQueryParams, request
        )
    )

    total, messages = await _conversations_service.list_project_conversation_messages(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
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


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="update_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def update_project_conversation_message(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsMessagesPathParams, request
    )
    body_params = await parse_request_body_as(
        _ProjectConversationMessagesPutBodyParams, request
    )

    message = await _conversations_service.update_project_conversation_message(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
        content=body_params.content,
    )
    data = ConversationMessageRestGet.from_domain_model(message)

    return envelope_json_response(data)


@routes.delete(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="delete_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def delete_project_conversation_message(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsMessagesPathParams, request
    )

    await _conversations_service.delete_project_conversation_message(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/conversations/{{conversation_id}}/messages/{{message_id}}",
    name="get_project_conversation_message",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_conversation_message(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        _ProjectConversationsMessagesPathParams, request
    )

    message = await _conversations_service.get_project_conversation_message(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
    )
    data = ConversationMessageRestGet.from_domain_model(message)

    return envelope_json_response(data)
