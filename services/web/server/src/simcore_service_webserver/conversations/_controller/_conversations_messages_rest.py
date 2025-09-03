import functools
import json
import logging
from typing import Any

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.api_schemas_webserver.conversations import (
    ConversationMessagePatch,
    ConversationMessageRestGet,
)
from models_library.conversations import (
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
    ConversationPatchDB,
    ConversationType,
)
from models_library.rest_pagination import (
    Page,
    PageQueryParameters,
)
from models_library.rest_pagination_utils import paginate_data
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from ..._meta import API_VTAG as VTAG
from ...email import email_service
from ...fogbugz import get_fogbugz_rest_client
from ...fogbugz._client import FogbugzCaseCreate
from ...fogbugz.settings import FogbugzSettings
from ...login.decorators import login_required
from ...models import AuthenticatedRequestContext
from ...products import products_web
from ...users import users_service
from ...utils_aiohttp import envelope_json_response
from .. import _conversation_message_service, _conversation_service
from ._common import ConversationPathParams, raise_unsupported_type
from ._rest_exceptions import _handle_exceptions

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class _ConversationMessagePathParams(ConversationPathParams):
    message_id: ConversationMessageID
    model_config = ConfigDict(extra="forbid")


class _ListConversationMessageQueryParams(PageQueryParameters):

    model_config = ConfigDict(extra="forbid")


class _ConversationMessageCreateBodyParams(BaseModel):
    content: str
    type: ConversationMessageType
    model_config = ConfigDict(extra="forbid")


def _json_encoder_and_dumps(obj: Any, **kwargs):
    return json_dumps(jsonable_encoder(obj), **kwargs)


@routes.post(
    f"/{VTAG}/conversations/{{conversation_id}}/messages",
    name="create_conversation_message",
)
@login_required
@_handle_exceptions
async def create_conversation_message(request: web.Request):
    """Create a new message in a conversation"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ConversationPathParams, request)
    body_params = await parse_request_body_as(
        _ConversationMessageCreateBodyParams, request
    )

    _conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if _conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(_conversation.type)

    # This function takes care of granting support user access to the message
    await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

    message, is_first_message = (
        await _conversation_message_service.create_support_message_with_first_check(
            app=request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            project_id=None,  # Support conversations don't use project_id
            conversation_id=path_params.conversation_id,
            content=body_params.content,
            type_=body_params.type,
        )
    )

    # NOTE: This is done here in the Controller layer, as the interface around email currently needs request
    product = products_web.get_current_product(request)
    fogbugz_settings_or_none: FogbugzSettings | None = request.app[
        APP_SETTINGS_KEY
    ].WEBSERVER_FOGBUGZ
    if (
        product.support_standard_group_id
        and fogbugz_settings_or_none is not None
        and is_first_message
    ):
        _logger.debug(
            "Support settings available and FogBugz client configured, creating FogBugz case."
        )
        assert product.support_assigned_fogbugz_project_id  # nosec

        try:
            user = await users_service.get_user(request.app, req_ctx.user_id)
            _url = request.url
            _conversation_url = f"{_url.scheme}://{_url.host}/#/conversation/{path_params.conversation_id}"

            _description = f"""
            Dear Support Team,

            We have received a support request from {user["first_name"]} {user["last_name"]} ({user["email"]}) on {request.host}.

            All communication should take place in the Platform Support Center at the following link: {_conversation_url}

            First message content: {message.content}

            Extra content: {json.dumps(_conversation.extra_context)}
            """

            _fogbugz_client = get_fogbugz_rest_client(request.app)
            _fogbugz_case_data = FogbugzCaseCreate(
                fogbugz_project_id=product.support_assigned_fogbugz_project_id,
                title=f"Request for Support on {request.host}",
                description=_description,
            )
            _case_id = await _fogbugz_client.create_case(_fogbugz_case_data)

            await _conversation_service.update_conversation(
                request.app,
                project_id=None,
                conversation_id=_conversation.conversation_id,
                updates=ConversationPatchDB(
                    name=None,
                    extra_context=_conversation.extra_context
                    | {"fogbugz_case_id": _case_id},
                ),
            )
        except Exception:  # pylint: disable=broad-except
            _logger.exception(
                "Failed to create support request FogBugz case for conversation %s.",
                _conversation.conversation_id,
            )

    elif (
        product.support_standard_group_id
        and fogbugz_settings_or_none is None
        and is_first_message
    ):
        _logger.debug(
            "Support settings available, but no FogBugz client configured, sending email instead to create FogBugz case."
        )
        try:
            user = await users_service.get_user(request.app, req_ctx.user_id)
            template_name = "request_support.jinja2"
            destination_email = product.support_email
            email_template_path = await products_web.get_product_template_path(
                request, template_name
            )
            _url = request.url
            _conversation_url = f"{_url.scheme}://{_url.host}/#/conversation/{path_params.conversation_id}"
            _extra_context = _conversation.extra_context
            await email_service.send_email_from_template(
                request,
                from_=product.support_email,
                to=destination_email,
                template=email_template_path,
                context={
                    "host": request.host,
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "user_email": user["email"],
                    "conversation_url": _conversation_url,
                    "message_content": message.content,
                    "extra_context": _extra_context,
                    "dumps": functools.partial(_json_encoder_and_dumps, indent=1),
                },
            )
        except Exception:  # pylint: disable=broad-except
            _logger.exception(
                "Failed to send '%s' email to %s (this means the FogBugz case for the request was not created).",
                template_name,
                destination_email,
            )
    else:
        _logger.debug("No support settings available, skipping FogBugz case creation.")

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
    path_params = parse_request_path_parameters_as(ConversationPathParams, request)
    query_params = parse_request_query_parameters_as(
        _ListConversationMessageQueryParams, request
    )

    _conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if _conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(_conversation.type)

    # This function takes care of granting support user access to the message
    await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

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

    _conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if _conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(_conversation.type)

    # This function takes care of granting support user access to the message
    await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

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

    _conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if _conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(_conversation.type)

    # This function takes care of granting support user access to the message
    await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

    message = await _conversation_message_service.update_message(
        app=request.app,
        product_name=req_ctx.product_name,
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

    _conversation = await _conversation_service.get_conversation(
        request.app, conversation_id=path_params.conversation_id
    )
    if _conversation.type != ConversationType.SUPPORT:
        raise_unsupported_type(_conversation.type)

    # This function takes care of granting support user access to the message
    await _conversation_service.get_support_conversation_for_user(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        conversation_id=path_params.conversation_id,
    )

    await _conversation_message_service.delete_message(
        app=request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=None,  # Support conversations don't use project_id
        conversation_id=path_params.conversation_id,
        message_id=path_params.message_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
