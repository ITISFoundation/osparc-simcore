import datetime
from typing import Final

from aiohttp import web
from models_library.conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
    ConversationMessageType,
    ConversationName,
    ConversationType,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from servicelib.utils import limited_as_completed

from ..socketio.messages import send_message_to_user

_MAX_CONCURRENT_SENDS: Final[int] = 3

SOCKET_IO_CONVERSATION_CREATED_EVENT: Final[str] = "conversation:created"
SOCKET_IO_CONVERSATION_DELETED_EVENT: Final[str] = "conversation:deleted"
SOCKET_IO_CONVERSATION_UPDATED_EVENT: Final[str] = "conversation:updated"

SOCKET_IO_CONVERSATION_MESSAGE_CREATED_EVENT: Final[str] = (
    "conversation:message:created"
)
SOCKET_IO_CONVERSATION_MESSAGE_DELETED_EVENT: Final[str] = (
    "conversation:message:deleted"
)
SOCKET_IO_CONVERSATION_MESSAGE_UPDATED_EVENT: Final[str] = (
    "conversation:message:updated"
)


class BaseEvent(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
    )


class BaseConversationEvent(BaseEvent):
    product_name: ProductName
    project_id: ProjectID | None
    user_group_id: GroupID
    conversation_id: ConversationID
    type: ConversationType


class ConversationCreatedOrUpdatedEvent(BaseConversationEvent):
    name: ConversationName
    created: datetime.datetime
    modified: datetime.datetime


class ConversationDeletedEvent(BaseConversationEvent): ...


class BaseConversationMessageEvent(BaseEvent):
    conversation_id: ConversationID
    message_id: ConversationMessageID
    user_group_id: GroupID
    type: ConversationMessageType

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
    )


class ConversationMessageCreatedOrUpdatedEvent(BaseConversationMessageEvent):
    content: str
    created: datetime.datetime
    modified: datetime.datetime


class ConversationMessageDeletedEvent(BaseConversationMessageEvent): ...


async def _send_message_to_recipients(
    app: web.Application,
    recipients: set[UserID],
    notification_message: SocketMessageDict,
):
    async for _ in limited_as_completed(
        (
            send_message_to_user(app, recipient, notification_message)
            for recipient in recipients
        ),
        limit=_MAX_CONCURRENT_SENDS,
    ):
        ...


async def notify_conversation_created(
    app: web.Application,
    *,
    recipients: set[UserID],
    project_id: ProjectID,
    conversation: ConversationGetDB,
) -> None:
    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_CREATED_EVENT,
        data={
            **ConversationCreatedOrUpdatedEvent(
                project_id=project_id,
                **conversation.model_dump(),
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_updated(
    app: web.Application,
    *,
    recipients: set[UserID],
    project_id: ProjectID,
    conversation: ConversationGetDB,
) -> None:
    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_UPDATED_EVENT,
        data={
            **ConversationCreatedOrUpdatedEvent(
                project_id=project_id,
                **conversation.model_dump(),
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_deleted(
    app: web.Application,
    *,
    recipients: set[UserID],
    product_name: ProductName,
    user_group_id: GroupID,
    project_id: ProjectID,
    conversation_id: ConversationID,
) -> None:
    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_DELETED_EVENT,
        data={
            **ConversationDeletedEvent(
                product_name=product_name,
                project_id=project_id,
                conversation_id=conversation_id,
                user_group_id=user_group_id,
                type=ConversationType.PROJECT_STATIC,
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


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
            **ConversationMessageCreatedOrUpdatedEvent(
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
            **ConversationMessageCreatedOrUpdatedEvent(
                **conversation_message.model_dump()
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)


async def notify_conversation_message_deleted(
    app: web.Application,
    *,
    recipients: set[UserID],
    user_group_id: GroupID,
    project_id: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:

    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_CONVERSATION_MESSAGE_DELETED_EVENT,
        data={
            "projectId": project_id,
            **ConversationMessageDeletedEvent(
                conversation_id=conversation_id,
                message_id=message_id,
                user_group_id=user_group_id,
                type=ConversationMessageType.MESSAGE,
            ).model_dump(mode="json", by_alias=True),
        },
    )

    await _send_message_to_recipients(app, recipients, notification_message)
