# pylint: disable=unused-argument

import json
import logging
from typing import Any
from urllib.parse import urljoin

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationPatchDB,
    ConversationType,
    ConversationUserType,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageTotalCount
from models_library.users import UserID

from ..conversations._socketio import (
    notify_via_socket_conversation_created,
    notify_via_socket_conversation_deleted,
    notify_via_socket_conversation_updated,
)
from ..fogbugz import FogbugzCaseCreate, get_fogbugz_rest_client
from ..groups import api as group_service
from ..groups.api import list_user_groups_ids_with_read_access
from ..products import products_service
from ..projects._groups_repository import list_project_groups
from ..users import users_service
from ..users._users_service import get_users_in_group
from . import _conversation_repository

_logger = logging.getLogger(__name__)


async def get_recipients_from_project(
    app: web.Application, project_id: ProjectID
) -> set[UserID]:
    groups = await list_project_groups(app, project_id=project_id)
    return {
        user
        for group in groups
        if group.read
        for user in await get_users_in_group(app, gid=group.gid)
    }


async def get_recipients_from_product_support_group(
    app: web.Application, product_name: ProductName
) -> set[UserID]:
    product = products_service.get_product(app, product_name=product_name)
    _support_standard_group_id = product.support_standard_group_id
    if _support_standard_group_id:
        users = await group_service.list_group_members(
            app, group_id=_support_standard_group_id
        )
        return {user.id for user in users}
    return set()


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
        await notify_via_socket_conversation_created(
            app,
            recipients=await get_recipients_from_project(app, project_uuid),
            project_id=project_uuid,
            conversation=created_conversation,
        )
    else:
        _product_group_users = await get_recipients_from_product_support_group(
            app, product_name=product_name
        )
        await notify_via_socket_conversation_created(
            app,
            recipients=_product_group_users | {user_id},
            project_id=None,
            conversation=created_conversation,
        )

    return created_conversation


async def get_conversation(
    app: web.Application,
    *,
    conversation_id: ConversationID,
) -> ConversationGetDB:
    return await _conversation_repository.get(
        app,
        conversation_id=conversation_id,
    )


async def get_conversation_for_user(
    app: web.Application,
    *,
    conversation_id: ConversationID,
    user_group_id: UserID,
) -> ConversationGetDB:
    return await _conversation_repository.get_for_user(
        app,
        conversation_id=conversation_id,
        user_group_id=user_group_id,
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
        await notify_via_socket_conversation_updated(
            app,
            recipients=await get_recipients_from_project(app, project_id),
            project_id=project_id,
            conversation=updated_conversation,
        )
    else:
        _product_group_users = await get_recipients_from_product_support_group(
            app, product_name=updated_conversation.product_name
        )
        _conversation_creator_user = await users_service.get_user_id_from_gid(
            app, primary_gid=updated_conversation.user_group_id
        )
        await notify_via_socket_conversation_updated(
            app,
            recipients=_product_group_users | {_conversation_creator_user},
            project_id=None,
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
    conversation_type: ConversationType,
) -> None:
    await _conversation_repository.delete(
        app,
        conversation_id=conversation_id,
    )

    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)

    if project_id:
        await notify_via_socket_conversation_deleted(
            app,
            recipients=await get_recipients_from_project(app, project_id),
            product_name=product_name,
            user_group_id=_user_group_id,
            project_id=project_id,
            conversation_id=conversation_id,
            conversation_type=conversation_type,
        )
    else:
        _product_group_users = await get_recipients_from_product_support_group(
            app, product_name=product_name
        )
        await notify_via_socket_conversation_deleted(
            app,
            recipients=_product_group_users | {user_id},
            product_name=product_name,
            user_group_id=_user_group_id,
            project_id=None,
            conversation_id=conversation_id,
            conversation_type=conversation_type,
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
) -> tuple[ConversationGetDB, ConversationUserType]:
    # Check if user is part of support group (in that case he has access to all support conversations)
    product = products_service.get_product(app, product_name=product_name)
    _support_standard_group_id = product.support_standard_group_id
    _chatbot_user_id = product.support_chatbot_user_id

    # Check if user is an AI bot
    if _chatbot_user_id and user_id == _chatbot_user_id:
        conversation = await get_conversation(app, conversation_id=conversation_id)
        assert conversation.type.is_support_type()  # nosec
        return (
            conversation,
            ConversationUserType.CHATBOT_USER,
        )

    if _support_standard_group_id is not None:
        _user_group_ids = await list_user_groups_ids_with_read_access(
            app, user_id=user_id
        )
        if _support_standard_group_id in _user_group_ids:
            # I am a support user
            conversation = await get_conversation(app, conversation_id=conversation_id)
            assert conversation.type.is_support_type()  # nosec
            return (
                conversation,
                ConversationUserType.SUPPORT_USER,
            )

    # I am a regular user
    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
    conversation = await get_conversation_for_user(
        app,
        conversation_id=conversation_id,
        user_group_id=_user_group_id,
    )
    assert conversation.type.is_support_type()  # nosec
    return (
        conversation,
        ConversationUserType.REGULAR_USER,
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
                product_name=product_name,
                offset=offset,
                limit=limit,
                order_by=OrderBy(
                    field=IDStr("last_message_created_at"),
                    direction=OrderDirection.DESC,
                ),
            )

    _user_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
    return await _conversation_repository.list_support_conversations_for_user(
        app,
        user_group_id=_user_group_id,
        product_name=product_name,
        offset=offset,
        limit=limit,
        order_by=OrderBy(
            field=IDStr("last_message_created_at"), direction=OrderDirection.DESC
        ),
    )


async def create_fogbugz_case_for_support_conversation(
    app: web.Application,
    *,
    conversation: ConversationGetDB,
    user_id: UserID,
    message_content: str,
    conversation_url: str,
    host: str,
    product_support_assigned_fogbugz_project_id: int,
    fogbugz_url: str,
) -> None:
    """Creates a FogBugz case for a support conversation and updates the conversation with the case URL."""
    user = await users_service.get_user(app, user_id)

    description = f"""
    Dear Support Team,

    We have received a support request from {user["first_name"]} {user["last_name"]} ({user["email"]}) on {host}.

    All communication should take place in the Platform Support Center at the following link: {conversation_url}

    First message content: {message_content}

    Extra content: {json.dumps(conversation.extra_context)}
    """

    fogbugz_client = get_fogbugz_rest_client(app)
    fogbugz_case_data = FogbugzCaseCreate(
        fogbugz_project_id=product_support_assigned_fogbugz_project_id,
        title=f"Request for Support on {host} by {user['email']}",
        description=description,
    )
    case_id = await fogbugz_client.create_case(fogbugz_case_data)

    # Update conversation with FogBugz case URL
    await update_conversation(
        app,
        project_id=None,
        conversation_id=conversation.conversation_id,
        updates=ConversationPatchDB(
            extra_context=conversation.extra_context
            | {
                "fogbugz_case_url": urljoin(
                    f"{fogbugz_url}",
                    f"f/cases/{case_id}",
                )
            },
            fogbugz_case_id=case_id,
        ),
    )


async def reopen_fogbugz_case_for_support_conversation(
    app: web.Application,
    *,
    case_id: str,
    conversation_url: str,
    product_support_assigned_fogbugz_person_id: str,
) -> None:
    """Reopen a FogBugz case for a support conversation"""
    description = f"""
    Dear Support Team,

    We have received a follow up request in this conversation {conversation_url}.
    """

    fogbugz_client = get_fogbugz_rest_client(app)
    await fogbugz_client.reopen_case(
        case_id=case_id,
        assigned_fogbugz_person_id=product_support_assigned_fogbugz_person_id,
        reopen_msg=description,
    )
