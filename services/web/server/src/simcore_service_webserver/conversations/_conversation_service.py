# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationPatchDB,
    ConversationType,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageTotalCount
from models_library.users import UserID

from ..users.api import get_user_primary_group_id
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
) -> ConversationGetDB:
    if project_uuid is None:
        raise NotImplementedError

    _user_group_id = await get_user_primary_group_id(app, user_id=user_id)

    return await _conversation_repository.create(
        app,
        name=name,
        project_uuid=project_uuid,
        user_group_id=_user_group_id,
        type_=type_,
        product_name=product_name,
    )


async def get_conversation(
    app: web.Application,
    *,
    conversation_id: ConversationID,
) -> ConversationGetDB:
    return await _conversation_repository.get(
        app,
        conversation_id=conversation_id,
    )


async def update_conversation(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    # Update attributes
    updates: ConversationPatchDB,
) -> ConversationGetDB:
    return await _conversation_repository.update(
        app,
        conversation_id=conversation_id,
        updates=updates,
    )


async def delete_conversation(
    app: web.Application,
    *,
    conversation_id: ConversationID,
) -> None:
    await _conversation_repository.delete(
        app,
        conversation_id=conversation_id,
    )


async def list_conversations_for_project(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    # pagination
    offset: int = 0,
    limit: int = 20,
) -> tuple[PageTotalCount, list[ConversationGetDB]]:
    return await _conversation_repository.list_project_conversations(
        app,
        project_uuid=project_uuid,
        offset=offset,
        limit=limit,
        order_by=OrderBy(field=IDStr("conversation_id"), direction=OrderDirection.DESC),
    )
