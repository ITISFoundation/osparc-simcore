import asyncio
import datetime
from typing import Final

from aiohttp import web
from models_library.conversations import (
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
)
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.socketio import SocketMessageDict
from pydantic import BaseModel

from ..socketio.messages import send_message_to_standard_group

SOCKET_IO_CONVERSATION_MESSAGE_CREATED_EVENT: Final[str] = "conversationMessageCreated"

SOCKET_IO_CONVERSATION_MESSAGE_DELETED_EVENT: Final[str] = "conversationMessageDeleted"

SOCKET_IO_CONVERSATION_MESSAGE_UPDATED_EVENT: Final[str] = "conversationMessageUpdated"


class ConversationMessage(BaseModel):
    conversation_id: ConversationID
    message_id: ConversationMessageID


class ConversationMessageCreated(ConversationMessage):
    content: str
    created: datetime.datetime


class ConversationMessageUpdated(ConversationMessage):
    content: str
    modified: datetime.datetime


class ConversationMessageDeleted(ConversationMessage): ...


async def _send_message_to_recipients(app, recipients, notification_message):
    await asyncio.gather(
        *[
            send_message_to_standard_group(app, recipient, notification_message)
            for recipient in recipients
        ]
    )


async def notify_conversation_message_created(
    app: web.Application,
    *,
    recipients: list[GroupID],
    project_id: ProjectID,
    conversation_message: ConversationMessageGetDB,
) -> None:
    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_CREATED_EVENT,
        data={
            "project_id": project_id,
            **ConversationMessageCreated(
                **conversation_message.model_dump()
            ).model_dump(mode="json"),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_message_updated(
    app: web.Application,
    *,
    recipients: list[GroupID],
    project_id: ProjectID,
    conversation_message: ConversationMessageGetDB,
) -> None:

    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_UPDATED_EVENT,
        data={
            "project_id": project_id,
            **ConversationMessageUpdated(
                **conversation_message.model_dump()
            ).model_dump(mode="json"),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_message_deleted(
    app: web.Application,
    *,
    recipients: list[GroupID],
    project_id: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:

    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_DELETED_EVENT,
        data={
            "project_id": project_id,
            **ConversationMessageDeleted(
                conversation_id=conversation_id, message_id=message_id
            ).model_dump(mode="json"),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)
