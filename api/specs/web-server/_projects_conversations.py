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
    ConversationMessageRestGet,
    ConversationRestGet,
)
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._controller._rest_schemas import (
    ProjectPathParams,
)
from simcore_service_webserver.projects._controller.conversations_rest import (
    _ListProjectConversationMessagesQueryParams,
    _ListProjectConversationsQueryParams,
    _ProjectConversationMessagesCreateBodyParams,
    _ProjectConversationMessagesPutBodyParams,
    _ProjectConversationsCreateBodyParams,
    _ProjectConversationsMessagesPathParams,
    _ProjectConversationsPathParams,
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
    status_code=status.HTTP_201_CREATED,
)
async def create_project_conversation(
    _params: Annotated[ProjectPathParams, Depends()],
    _body: _ProjectConversationsCreateBodyParams,
): ...


@router.get(
    "/projects/{project_id}/conversations",
    response_model=Page[ConversationRestGet],
)
async def list_project_conversations(
    _params: Annotated[ProjectPathParams, Depends()],
    _query: Annotated[_ListProjectConversationsQueryParams, Depends()],
): ...


@router.put(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=Envelope[ConversationRestGet],
)
async def update_project_conversation(
    _params: Annotated[_ProjectConversationsPathParams, Depends()],
    _body: _ProjectConversationsPutBodyParams,
): ...


@router.delete(
    "/projects/{project_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_conversation(
    _params: Annotated[_ProjectConversationsPathParams, Depends()],
): ...


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=Envelope[ConversationRestGet],
)
async def get_project_conversation(
    _params: Annotated[_ProjectConversationsPathParams, Depends()],
): ...


### Conversation Messages


@router.post(
    "/projects/{project_id}/conversations/{conversation_id}/messages",
    response_model=Envelope[ConversationMessageRestGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_project_conversation_message(
    _params: Annotated[_ProjectConversationsPathParams, Depends()],
    _body: _ProjectConversationMessagesCreateBodyParams,
): ...


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}/messages",
    response_model=Page[ConversationMessageRestGet],
)
async def list_project_conversation_messages(
    _params: Annotated[_ProjectConversationsPathParams, Depends()],
    _query: Annotated[_ListProjectConversationMessagesQueryParams, Depends()],
): ...


@router.put(
    "/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}",
    response_model=Envelope[ConversationMessageRestGet],
)
async def update_project_conversation_message(
    _params: Annotated[_ProjectConversationsMessagesPathParams, Depends()],
    _body: _ProjectConversationMessagesPutBodyParams,
): ...


@router.delete(
    "/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_conversation_message(
    _params: Annotated[_ProjectConversationsMessagesPathParams, Depends()],
): ...


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}",
    response_model=Envelope[ConversationMessageRestGet],
)
async def get_project_conversation_message(
    _params: Annotated[_ProjectConversationsMessagesPathParams, Depends()],
): ...
