"""Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter
from models_library.api_schemas_webserver.projects_conversations import (
    ConversationMessageRestGet,
    ConversationRestGet,
)
from models_library.conversations import ConversationID, ConversationMessageID
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_conversations import conversationID
from models_library.rest_pagination import Page
from pydantic import NonNegativeInt
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._controller.conversations_rest import (
    _ListProjectConversationMessagesQueryParams,
    _ListProjectConversationsQueryParams,
    _ProjectConversationMessagesCreateBodyParams,
    _ProjectConversationMessagesPutBodyParams,
    _ProjectConversationsCreateBodyParams,
    _ProjectConversationsPutBodyParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "conversations",
    ],
)


#
# API entrypoints PROJECTS/*/CONVERSATIONS/*
#


@router.post(
    "/projects/{project_id}/conversations",
    response_model=Envelope[ConversationRestGet],
    status_code=201,
)
async def create_project_conversation(
    project_id: ProjectID, body: _ProjectConversationsCreateBodyParams
): ...


assert_handler_signature_against_model(
    create_project_conversation, _ProjectConversationsCreateBodyParams
)


@router.get(
    "/projects/{project_id}/conversations",
    response_model=Page[ConversationRestGet],
)
async def list_project_conversations(
    project_id: ProjectID, limit: int = 20, offset: NonNegativeInt = 0
): ...


assert_handler_signature_against_model(
    list_project_conversations, _ListProjectConversationsQueryParams
)


@router.put(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=Envelope[ConversationRestGet],
)
async def update_project_conversation(
    project_id: ProjectID,
    conversation_id: ConversationID,
    body: _ProjectConversationsPutBodyParams,
): ...


assert_handler_signature_against_model(
    update_project_conversation, _ProjectConversationsPutBodyParams
)


@router.delete(
    "/projects/{project_id}/conversations/{conversation_id}",
    status_code=204,
)
async def delete_project_conversation(
    project_id: ProjectID, conversation_id: conversationID
): ...


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=Envelope[ConversationRestGet],
)
async def get_project_conversation(
    project_id: ProjectID, conversation_id: conversationID
): ...


#
# API entrypoints PROJECTS/*/CONVERSATIONS/*/MESSAGES/*
#


@router.post(
    "/projects/{project_id}/conversations/{conversation_id}/messages",
    response_model=Envelope[ConversationMessageRestGet],
    status_code=201,
)
async def create_project_conversation_message(
    project_id: ProjectID,
    conversation_id: ConversationID,
    body: _ProjectConversationMessagesCreateBodyParams,
): ...


assert_handler_signature_against_model(
    create_project_conversation_message, _ProjectConversationMessagesCreateBodyParams
)


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}/messages",
    response_model=Page[ConversationMessageRestGet],
)
async def list_project_conversation_messages(
    project_id: ProjectID, limit: int = 20, offset: NonNegativeInt = 0
): ...


assert_handler_signature_against_model(
    list_project_conversation_messages, _ListProjectConversationMessagesQueryParams
)


@router.put(
    "/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}",
    response_model=Envelope[ConversationMessageRestGet],
)
async def update_project_conversation_message(
    project_id: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
    body: _ProjectConversationMessagesPutBodyParams,
): ...


assert_handler_signature_against_model(
    update_project_conversation_message, _ProjectConversationMessagesPutBodyParams
)


@router.delete(
    "/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}",
    status_code=204,
)
async def delete_project_conversation_message(
    project_id: ProjectID,
    conversation_id: conversationID,
    message_id: ConversationMessageID,
): ...


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}",
    response_model=Envelope[ConversationMessageRestGet],
)
async def get_project_conversation_message(
    project_id: ProjectID,
    conversation_id: conversationID,
    message_id: ConversationMessageID,
): ...
