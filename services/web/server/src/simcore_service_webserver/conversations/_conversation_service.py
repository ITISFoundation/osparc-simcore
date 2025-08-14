# pylint: disable=unused-argument

import logging
from typing import Any

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

from ..conversations._socketio import (
    notify_conversation_created,
    notify_conversation_deleted,
    notify_conversation_updated,
)
from ..groups.api import list_user_groups_ids_with_read_access
from ..products import products_service
from ..projects._groups_repository import list_project_groups
from ..users import users_service
from ..users._users_service import get_users_in_group
from . import _conversation_repository

_logger = logging.getLogger(__name__)


async def _get_recipients(app: web.Application, project_id: ProjectID) -> set[UserID]:
    groups = await list_project_groups(app, project_id=project_id)
    return {
        user
        for group in groups
        if group.read
        for user in await get_users_in_group(app, gid=group.gid)
    }


async def create_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID | None,
    # Creation attributes
    name: str,
    type_: ConversationType,
    extra_context: dict[str, Any],
) -> ConversationGetDB:
    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)

    created_conversation = await _conversation_repository.create(
        app,
        name=name,
        project_uuid=project_uuid,
        user_group_id=_user_group_id,
        type_=type_,
        product_name=product_name,
        extra_context=extra_context,
    )

    if project_uuid:
        await notify_conversation_created(
            app,
            recipients=await _get_recipients(app, project_uuid),
            project_id=project_uuid,
            conversation=created_conversation,
        )

    return created_conversation


async def get_conversation(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    # filters
    type_: ConversationType | None = None,
) -> ConversationGetDB:
    return await _conversation_repository.get(
        app,
        conversation_id=conversation_id,
        type=type_,
    )


async def get_conversation_for_user(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    user_group_id: UserID,
    type_: ConversationType | None = None,
) -> ConversationGetDB:
    return await _conversation_repository.get_for_user(
        app,
        conversation_id=conversation_id,
        user_group_id=user_group_id,
        type_=type_,
    )


async def update_conversation(
    app: web.Application,
    *,
    project_id: ProjectID | None,
    conversation_id: ConversationID,
    # Update attributes
    updates: ConversationPatchDB,
) -> ConversationGetDB:
    updated_conversation = await _conversation_repository.update(
        app,
        conversation_id=conversation_id,
        updates=updates,
    )

    if project_id:
        await notify_conversation_updated(
            app,
            recipients=await _get_recipients(app, project_id),
            project_id=project_id,
            conversation=updated_conversation,
        )

    return updated_conversation


async def delete_conversation(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID | None,
    conversation_id: ConversationID,
) -> None:
    await _conversation_repository.delete(
        app,
        conversation_id=conversation_id,
    )

    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)

    if project_id:
        await notify_conversation_deleted(
            app,
            recipients=await _get_recipients(app, project_id),
            product_name=product_name,
            user_group_id=_user_group_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )


async def list_project_conversations(
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


async def get_support_conversation_for_user(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    conversation_id: ConversationID,
):
    # Check if user is part of support group (in that case he has access to all support conversations)
    product = products_service.get_product(app, product_name=product_name)
    _support_standard_group_id = product.support_standard_group_id
    if _support_standard_group_id is not None:
        _user_group_ids = await list_user_groups_ids_with_read_access(
            app, user_id=user_id
        )
        if _support_standard_group_id in _user_group_ids:
            # I am a support user
            return await get_conversation(
                app, conversation_id=conversation_id, type_=ConversationType.SUPPORT
            )

    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
    return await get_conversation_for_user(
        app,
        conversation_id=conversation_id,
        user_group_id=_user_group_id,
        type_=ConversationType.SUPPORT,
    )


async def list_support_conversations_for_user(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    # pagination
    offset: int = 0,
    limit: int = 20,
) -> tuple[PageTotalCount, list[ConversationGetDB]]:

    # Check if user is part of support group (in that case list all support conversations)
    product = products_service.get_product(app, product_name=product_name)
    _support_standard_group_id = product.support_standard_group_id
    if _support_standard_group_id is not None:
        _user_group_ids = await list_user_groups_ids_with_read_access(
            app, user_id=user_id
        )
        if _support_standard_group_id in _user_group_ids:
            # I am a support user
            return await _conversation_repository.list_all_support_conversations_for_support_user(
                app,
                offset=offset,
                limit=limit,
                order_by=OrderBy(
                    field=IDStr("conversation_id"), direction=OrderDirection.DESC
                ),
            )

    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
    return await _conversation_repository.list_support_conversations_for_user(
        app,
        user_group_id=_user_group_id,
        offset=offset,
        limit=limit,
        order_by=OrderBy(field=IDStr("conversation_id"), direction=OrderDirection.DESC),
    )
