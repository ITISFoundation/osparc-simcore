import logging

from aiohttp import web
from models_library.conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
    ConversationName,
    ConversationPatchDB,
    ConversationType,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import PositiveInt

from ..conversations import conversations_service
from ._access_rights_service import check_user_project_permission

_logger = logging.getLogger(__name__)


#
#  PROJECT CONVERSATION -------------------------------------------------------------------
#


async def create_project_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    # attributes
    name: str,
    conversation_type: ConversationType,
) -> ConversationGetDB:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.create_conversation(
        app,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        name=name,
        type_=conversation_type,
    )


async def list_project_conversations(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    # pagination
    offset: PositiveInt,
    limit: int,
) -> tuple[int, list[ConversationGetDB]]:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.list_conversations_for_project(
        app,
        project_uuid=project_uuid,
        offset=offset,
        limit=limit,
    )


async def update_project_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
    # attributes
    name: ConversationName,
) -> ConversationGetDB:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.update_conversation(
        app,
        project_id=project_uuid,
        conversation_id=conversation_id,
        updates=ConversationPatchDB(name=name),
    )


async def delete_project_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
) -> None:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    await conversations_service.delete_conversation(
        app,
        product_name=product_name,
        project_id=project_uuid,
        user_id=user_id,
        conversation_id=conversation_id,
    )


async def get_project_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
) -> ConversationGetDB:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.get_conversation(
        app, conversation_id=conversation_id
    )


#
#  PROJECT CONVERSATION MESSAGES -------------------------------------------------------------------
#


async def create_project_conversation_message(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
    # attributes
    content: str,
    message_type: ConversationMessageType,
) -> ConversationMessageGetDB:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.create_message(
        app,
        user_id=user_id,
        project_id=project_uuid,
        conversation_id=conversation_id,
        content=content,
        type_=message_type,
    )


async def list_project_conversation_messages(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
    # pagination
    offset: PositiveInt,
    limit: int,
) -> tuple[int, list[ConversationMessageGetDB]]:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.list_messages_for_conversation(
        app,
        conversation_id=conversation_id,
        offset=offset,
        limit=limit,
    )


async def update_project_conversation_message(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
    # attributes
    content: str,
) -> ConversationMessageGetDB:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.update_message(
        app,
        project_id=project_uuid,
        conversation_id=conversation_id,
        message_id=message_id,
        updates=ConversationMessagePatchDB(content=content),
    )


async def delete_project_conversation_message(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    await conversations_service.delete_message(
        app,
        user_id=user_id,
        project_id=project_uuid,
        conversation_id=conversation_id,
        message_id=message_id,
    )


async def get_project_conversation_message(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> ConversationMessageGetDB:
    await check_user_project_permission(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )
    return await conversations_service.get_message(
        app, conversation_id=conversation_id, message_id=message_id
    )
