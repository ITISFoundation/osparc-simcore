"""Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.conversations import (
    ConversationMessagePatch,
    ConversationMessageRestGet,
    ConversationPatch,
    ConversationRestGet,
)
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.conversations._controller._common import (
    ConversationPathParams,
)
from simcore_service_webserver.conversations._controller.conversations_messages_rest import (
    _ConversationMessageCreateBodyParams,
    _ConversationMessagePathParams,
    _ListConversationMessageQueryParams,
)
from simcore_service_webserver.conversations._controller.conversations_rest import (
    _ConversationsCreateBodyParams,
    _GetConversationsQueryParams,
    _ListConversationsQueryParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "conversations",
    ],
)


#
# API entrypoints CONVERSATIONS
#


@router.post(
    "/conversations",
    response_model=Envelope[ConversationRestGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    _body: Annotated[_ConversationsCreateBodyParams, Depends()],
    _query: Annotated[_GetConversationsQueryParams, Depends()],
): ...


@router.get(
    "/conversations",
    response_model=Page[ConversationRestGet],
)
async def list_conversations(
    _query: Annotated[_ListConversationsQueryParams, Depends()],
): ...


@router.put(
    "/conversations/{conversation_id}",
    response_model=Envelope[ConversationRestGet],
)
async def update_conversation(
    _params: Annotated[ConversationPathParams, Depends()],
    _body: Annotated[ConversationPatch, Depends()],
    _query: Annotated[_GetConversationsQueryParams, Depends()],
): ...


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    _params: Annotated[ConversationPathParams, Depends()],
    _query: Annotated[_GetConversationsQueryParams, Depends()],
): ...


@router.get(
    "/conversations/{conversation_id}",
    response_model=Envelope[ConversationRestGet],
)
async def get_conversation(
    _params: Annotated[ConversationPathParams, Depends()],
    _query: Annotated[_GetConversationsQueryParams, Depends()],
): ...


#
# API entrypoints CONVERSATION MESSAGES
#


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=Envelope[ConversationMessageRestGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation_message(
    _params: Annotated[ConversationPathParams, Depends()],
    _body: _ConversationMessageCreateBodyParams,
): ...


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=Page[ConversationMessageRestGet],
)
async def list_conversation_messages(
    _params: Annotated[ConversationPathParams, Depends()],
    _query: Annotated[_ListConversationMessageQueryParams, Depends()],
): ...


@router.put(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=Envelope[ConversationMessageRestGet],
)
async def update_conversation_message(
    _params: Annotated[_ConversationMessagePathParams, Depends()],
    _body: ConversationMessagePatch,
): ...


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation_message(
    _params: Annotated[_ConversationMessagePathParams, Depends()],
): ...


@router.get(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=Envelope[ConversationMessageRestGet],
)
async def get_conversation_message(
    _params: Annotated[_ConversationMessagePathParams, Depends()],
): ...
