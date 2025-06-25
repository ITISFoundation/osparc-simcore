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

from ..projects._groups_repository import list_project_groups
from ..users._users_service import get_users_in_group

# Import or define SocketMessageDict
from ..users.api import get_user_primary_group_id
from . import _conversation_message_repository
from ._socketio import (
    notify_conversation_message_created,
    notify_conversation_message_deleted,
    notify_conversation_message_updated,
)

_logger = logging.getLogger(__name__)


async def _get_recipients(app: web.Application, project_id: ProjectID) -> set[UserID]:
    groups = await list_project_groups(app, project_id=project_id)
    return {
        user
        for group in groups
        if group.read
        for user in await get_users_in_group(app, gid=group.gid)
    }


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

    await notify_conversation_message_created(
        app,
        recipients=await _get_recipients(app, project_id),
        project_id=project_id,
        conversation_message=created_message,
    )

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
    project_id: ProjectID,
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
    project_id: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:
    await _conversation_message_repository.delete(
        app,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    _user_group_id = await get_user_primary_group_id(app, user_id=user_id)

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
