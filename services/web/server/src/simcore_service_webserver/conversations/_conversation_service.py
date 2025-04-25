# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.conversations import (
    ConversationDB,
    ConversationID,
    ConversationType,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID

from ..projects.api import check_user_project_permission
from . import _conversation_repository

_logger = logging.getLogger(__name__)


async def create_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID | None,
    # Creation attributes
    name: str,
    type_: ConversationType,
) -> ConversationDB:
    if project_uuid is None:
        raise NotImplementedError

    await check_user_project_permission(
        app=app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )

    return await _conversation_repository.create(
        app,
        name=name,
        project_uuid=project_uuid,
        user_id=user_id,
        type_=type_,
        product_name=product_name,
    )


async def get_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    conversation_id: ConversationID,
) -> ConversationDB:
    conversation = await _conversation_repository.get(
        app, conversation_id=conversation_id
    )
    assert conversation.project_uuid, "Not Implemented: Conversation has no project"

    await check_user_project_permission(
        app=app,
        product_name=product_name,
        user_id=user_id,
        project_id=conversation.project_uuid,
        permission="read",
    )

    return await _conversation_repository.get(
        app,
        conversation_id=conversation_id,
    )


async def update_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    conversation_id: ConversationID,
    # Update attributes
    updates,
) -> ConversationDB:
    conversation = await _conversation_repository.get(
        app, conversation_id=conversation_id
    )
    assert conversation.project_uuid, "Not Implemented: Conversation has no project"

    await check_user_project_permission(
        app=app,
        product_name=product_name,
        user_id=user_id,
        project_id=conversation.project_uuid,
        permission="read",
    )

    return await _conversation_repository.update(
        app,
        conversation_id=conversation_id,
        updates=updates,
    )


async def delete_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    conversation_id: ConversationID,
) -> None:
    conversation = await _conversation_repository.get(
        app, conversation_id=conversation_id
    )
    assert conversation.project_uuid, "Not Implemented: Conversation has no project"

    await check_user_project_permission(
        app=app,
        product_name=product_name,
        user_id=user_id,
        project_id=conversation.project_uuid,
        permission="write",
    )

    await _conversation_repository.delete(
        app,
        conversation_id=conversation_id,
    )


async def list_conversations_for_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    offset: int = 0,
    limit: int = 20,
) -> tuple[int, list[ConversationDB]]:
    await check_user_project_permission(
        app=app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_uuid,
        permission="read",
    )

    return await _conversation_repository.list_project_conversations(
        app,
        product_name=product_name,
        project_uuid=project_uuid,
        offset=offset,
        limit=limit,
        order_by=OrderBy(field="conversation_id", direction=OrderDirection.DESC),
    )
