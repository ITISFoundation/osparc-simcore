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
from models_library.users import UserID

# Import or define SocketMessageDict
from ..users import users_service
from . import _conversation_message_repository
from ._conversation_service import _get_recipients
from ._socketio import (
    notify_conversation_message_created,
    notify_conversation_message_deleted,
    notify_conversation_message_updated,
)

_logger = logging.getLogger(__name__)


async def create_message(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID | None,
    conversation_id: ConversationID,
    # Creation attributes
    content: str,
    type_: ConversationMessageType,
) -> ConversationMessageGetDB:
    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)

    created_message = await _conversation_message_repository.create(
        app,
        conversation_id=conversation_id,
        user_group_id=_user_group_id,
        content=content,
        type_=type_,
    )

    if project_id:
        await notify_conversation_message_created(
            app,
            recipients=await _get_recipients(app, project_id),
            project_id=project_id,
            conversation_message=created_message,
        )

    return created_message


async def create_support_message_and_check_if_it_is_first_message(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID | None,
    conversation_id: ConversationID,
    # Creation attributes
    content: str,
    type_: ConversationMessageType,
) -> tuple[ConversationMessageGetDB, bool]:
    created_message = await create_message(
        app,
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        content=content,
        type_=type_,
    )

    await _conversation_message_repository.list_(
        app,
        conversation_id=conversation_id,
        offset=0,
        limit=1,
        order_by=OrderBy(
            field=IDStr("created"), direction=OrderDirection.ASC
        ),  # NOTE: ASC - first/oldest message first
    )

    _, messages = await list_messages_for_conversation(
        app,
        conversation_id=conversation_id,
        offset=0,
        limit=1,
    )
    is_first_message = False
    if messages:
        first_message = messages[0]
        is_first_message = first_message.message_id == created_message.message_id

    return created_message, is_first_message


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
    project_id: ProjectID | None,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
    # Update attributes
    updates: ConversationMessagePatchDB,
) -> ConversationMessageGetDB:
    updated_message = await _conversation_message_repository.update(
        app,
        conversation_id=conversation_id,
        message_id=message_id,
        updates=updates,
    )

    if project_id:
        await notify_conversation_message_updated(
            app,
            recipients=await _get_recipients(app, project_id),
            project_id=project_id,
            conversation_message=updated_message,
        )

    return updated_message


async def delete_message(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID | None,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:
    await _conversation_message_repository.delete(
        app,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)

    if project_id:
        await notify_conversation_message_deleted(
            app,
            recipients=await _get_recipients(app, project_id),
            user_group_id=_user_group_id,
            project_id=project_id,
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
