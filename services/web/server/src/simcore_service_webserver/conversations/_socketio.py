import datetime
from typing import Final

from aiohttp import web
from models_library.conversations import (
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
)
from models_library.projects import ProjectID
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from servicelib.utils import limited_as_completed

from ..socketio.messages import send_message_to_standard_group

_MAX_CONCURRENT_SENDS: Final[int] = 3

SOCKET_IO_CONVERSATION_MESSAGE_CREATED_EVENT: Final[str] = (
    "conversation:message:created"
)
SOCKET_IO_CONVERSATION_MESSAGE_DELETED_EVENT: Final[str] = (
    "conversation:message:deleted"
)
SOCKET_IO_CONVERSATION_MESSAGE_UPDATED_EVENT: Final[str] = (
    "conversation:message:updated"
)


class BaseConversationMessage(BaseModel):
    conversation_id: ConversationID
    message_id: ConversationMessageID

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
    )


class ConversationMessageCreated(BaseConversationMessage):
    content: str
    created: datetime.datetime


class ConversationMessageUpdated(BaseConversationMessage):
    content: str
    modified: datetime.datetime


class ConversationMessageDeleted(BaseConversationMessage): ...


async def _send_message_to_recipients(
    app: web.Application,
    recipients: set[UserID],
    notification_message: SocketMessageDict,
):
    async for _ in limited_as_completed(
        (
            send_message_to_standard_group(app, recipient, notification_message)
            for recipient in recipients
        ),
        limit=_MAX_CONCURRENT_SENDS,
    ):
        ...


async def notify_conversation_message_created(
    app: web.Application,
    *,
    recipients: set[UserID],
    project_id: ProjectID,
    conversation_message: ConversationMessageGetDB,
) -> None:
    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_CREATED_EVENT,
        data={
            "projectId": project_id,
            **ConversationMessageCreated(
                **conversation_message.model_dump()
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_message_updated(
    app: web.Application,
    *,
    recipients: set[UserID],
    project_id: ProjectID,
    conversation_message: ConversationMessageGetDB,
) -> None:

    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_UPDATED_EVENT,
        data={
            "projectId": project_id,
            **ConversationMessageUpdated(
                **conversation_message.model_dump()
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_message_deleted(
    app: web.Application,
    *,
    recipients: set[UserID],
    project_id: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:

    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_DELETED_EVENT,
        data={
            "projectId": project_id,
            **ConversationMessageDeleted(
                conversation_id=conversation_id, message_id=message_id
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)
