# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.conversations import (
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
)
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageTotalCount
from models_library.socketio import SocketMessageDict
from models_library.users import UserID

from ..projects._groups_repository import list_project_groups

# Import or define SocketMessageDict
from ..socketio.messages import (
    SOCKET_IO_PROJECT_CONVERSATION_MESSAGE_CREATED_EVENT,
    send_message_to_standard_group,
)
from ..users.api import get_user_primary_group_id
from . import _conversation_message_repository

_logger = logging.getLogger(__name__)


def _make_project_conversation_message_created_message(
    project_id: ProjectID,
    conversation_message: ConversationMessageGetDB,
) -> SocketMessageDict:
    return SocketMessageDict(
        event_type=SOCKET_IO_PROJECT_CONVERSATION_MESSAGE_CREATED_EVENT,
        data={
            "project_id": project_id,
            **conversation_message.model_dump(mode="json"),
        },
    )


async def create_message(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    conversation_id: ConversationID,
    # Creation attributes
    content: str,
    type_: ConversationMessageType,
) -> ConversationMessageGetDB:
    _user_group_id = await get_user_primary_group_id(app, user_id=user_id)

    created_message = await _conversation_message_repository.create(
        app,
        conversation_id=conversation_id,
        user_group_id=_user_group_id,
        content=content,
        type_=type_,
    )

    recipients = [
        project_to_group.gid
        for project_to_group in await list_project_groups(app, project_id=project_id)
        if project_to_group.read
    ]

    for recipient in recipients:
        message = _make_project_conversation_message_created_message(
            project_id, created_message
        )
        await send_message_to_standard_group(app, recipient, message)

    return created_message


async def get_message(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> ConversationMessageGetDB:
    return await _conversation_message_repository.get(
        app, conversation_id=conversation_id, message_id=message_id
    )


async def update_message(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
    # Update attributes
    updates: ConversationMessagePatchDB,
) -> ConversationMessageGetDB:
    return await _conversation_message_repository.update(
        app,
        conversation_id=conversation_id,
        message_id=message_id,
        updates=updates,
    )


async def delete_message(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:
    await _conversation_message_repository.delete(
        app,
        conversation_id=conversation_id,
        message_id=message_id,
    )


async def list_messages_for_conversation(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    # pagination
    offset: int = 0,
    limit: int = 20,
) -> tuple[PageTotalCount, list[ConversationMessageGetDB]]:
    return await _conversation_message_repository.list_(
        app,
        conversation_id=conversation_id,
        offset=offset,
        limit=limit,
        order_by=OrderBy(
            field=IDStr("created"), direction=OrderDirection.DESC
        ),  # NOTE: Message should be ordered by creation date (latest first)
    )
