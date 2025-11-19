# pylint: disable=unused-argument

import logging

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.basic_types import IDStr
from models_library.conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
    ConversationPatchDB,
    ConversationType,
    ConversationUserType,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import WebserverChatbotRabbitMessage
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageTotalCount
from models_library.users import UserID

from ..application_keys import APP_SETTINGS_APPKEY
from ..groups import api as group_service
from ..products import products_service
from ..rabbitmq import get_rabbitmq_client
from ..users import users_service
from . import (
    _conversation_message_repository,
    _conversation_repository,
    _conversation_service,
)
from ._socketio import (
    notify_conversation_message_created,
    notify_conversation_message_deleted,
    notify_conversation_message_updated,
)
from .errors import ConversationError

_logger = logging.getLogger(__name__)

# Redis lock key for conversation message operations
CONVERSATION_MESSAGE_REDIS_LOCK_KEY = "conversation_message_update:{}"


async def _get_recipients_from_product_support_group(
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


async def create_message(
    app: web.Application,
    *,
    product_name: ProductName,
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
            recipients=await _conversation_service.get_recipients_from_project(
                app, project_id
            ),
            project_id=project_id,
            conversation_message=created_message,
        )
    else:
        _conversation = await _conversation_service.get_conversation(
            app, conversation_id=conversation_id
        )
        _conversation_creator_user = await users_service.get_user_id_from_gid(
            app, primary_gid=_conversation.user_group_id
        )
        _product_group_users = await _get_recipients_from_product_support_group(
            app, product_name=product_name
        )
        await notify_conversation_message_created(
            app,
            recipients=_product_group_users | {_conversation_creator_user},
            project_id=None,
            conversation_message=created_message,
        )

    return created_message


async def _create_support_message_with_first_check(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    conversation_user_type: ConversationUserType,
    conversation_id: ConversationID,
    # Creation attributes
    content: str,
    type_: ConversationMessageType,
) -> tuple[ConversationMessageGetDB, bool]:
    """Create a message and check if it's the first one with Redis lock protection.

    This function is protected by Redis exclusive lock because:
    - the message creation and first message check must be kept in sync

    Args:
        app: The web application instance
        user_id: ID of the user creating the message
        project_id: ID of the project (optional)
        conversation_id: ID of the conversation
        content: Content of the message
        type_: Type of the message

    Returns:
        Tuple containing the created message and whether it's the first message
    """

    # @exclusive(
    #     get_redis_lock_manager_client_sdk(app),
    #     lock_key=CONVERSATION_MESSAGE_REDIS_LOCK_KEY.format(conversation_id),
    #     blocking=True,
    #     blocking_timeout=None,  # NOTE: this is a blocking call, a timeout has undefined effects
    # )
    async def _create_support_message_and_check_if_it_is_first_message() -> (
        tuple[ConversationMessageGetDB, bool]
    ):
        """This function is protected because
        - the message creation and first message check must be kept in sync
        """
        created_message = await create_message(
            app,
            product_name=product_name,
            user_id=user_id,
            project_id=None,  # Support conversations don't use project_id
            conversation_id=conversation_id,
            content=content,
            type_=type_,
        )
        _, messages = await _conversation_message_repository.list_(
            app,
            conversation_id=conversation_id,
            offset=0,
            limit=1,
            order_by=OrderBy(
                field=IDStr("created"), direction=OrderDirection.ASC
            ),  # NOTE: ASC - first/oldest message first
        )

        is_first_message = False
        if messages:
            first_message = messages[0]
            is_first_message = first_message.message_id == created_message.message_id

        return created_message, is_first_message

    message, is_first_message = (
        await _create_support_message_and_check_if_it_is_first_message()
    )

    # NOTE: Update conversation last modified (for frontend listing) and read states
    match conversation_user_type:
        case ConversationUserType.REGULAR_USER:
            _is_read_by_user = True
            _is_read_by_support = False
        case ConversationUserType.SUPPORT_USER:
            _is_read_by_user = False
            _is_read_by_support = True
        case ConversationUserType.CHATBOT_USER:
            _is_read_by_user = False
            _is_read_by_support = False
        case _:
            msg = f"Unknown conversation user type: {conversation_user_type}"
            raise ConversationError(msg)

    await _conversation_repository.update(
        app,
        conversation_id=conversation_id,
        updates=ConversationPatchDB(
            is_read_by_user=_is_read_by_user,
            is_read_by_support=_is_read_by_support,
            last_message_created_at=message.created,
        ),
    )
    return message, is_first_message


async def _trigger_chatbot_processing(
    app: web.Application,
    conversation: ConversationGetDB,
    last_message_id: ConversationMessageID,
) -> None:
    """Triggers chatbot processing for a specific conversation."""
    rabbitmq_client = get_rabbitmq_client(app)
    message = WebserverChatbotRabbitMessage(
        conversation=conversation,
        last_message_id=last_message_id,
    )
    _logger.info(
        "Publishing chatbot processing message with conversation id %s and last message id %s.",
        conversation.conversation_id,
        last_message_id,
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def create_support_message(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    conversation_user_type: ConversationUserType,
    conversation: ConversationGetDB,
    # Creation attributes
    content: str,
    type_: ConversationMessageType,
) -> ConversationMessageGetDB:
    message, is_first_message = await _create_support_message_with_first_check(
        app=app,
        product_name=product_name,
        user_id=user_id,
        conversation_user_type=conversation_user_type,
        conversation_id=conversation.conversation_id,
        content=content,
        type_=type_,
    )

    product = products_service.get_product(app, product_name=product_name)
    fogbugz_settings_or_none = app[APP_SETTINGS_APPKEY].WEBSERVER_FOGBUGZ
    _conversation_url = (
        f"{product.base_url}#/conversation/{conversation.conversation_id}"
    )

    if (
        product.support_standard_group_id is None
        or product.support_assigned_fogbugz_project_id is None
        or product.support_assigned_fogbugz_person_id is None
        or fogbugz_settings_or_none is None
    ):
        _logger.warning(
            "Support settings NOT available, so no need to create FogBugz case. Conversation ID: %s",
            conversation.conversation_id,
        )

    elif is_first_message or conversation.fogbugz_case_id is None:
        _logger.info(
            "Support settings available, this is first message, creating FogBugz case for Conversation ID: %s",
            conversation.conversation_id,
        )
        assert product.support_assigned_fogbugz_project_id  # nosec

        try:
            await _conversation_service.create_fogbugz_case_for_support_conversation(
                app,
                conversation=conversation,
                user_id=user_id,
                message_content=message.content,
                conversation_url=_conversation_url,
                host=product.base_url.host or "unknown",
                product_support_assigned_fogbugz_project_id=product.support_assigned_fogbugz_project_id,
                fogbugz_url=str(fogbugz_settings_or_none.FOGBUGZ_URL),
            )
        except Exception as err:  # pylint: disable=broad-except
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Failed to create support request FogBugz case for conversation {conversation.conversation_id}.",
                    error=err,
                    error_context={
                        "conversation": conversation,
                        "user_id": user_id,
                        "fogbugz_url": str(fogbugz_settings_or_none.FOGBUGZ_URL),
                    },
                    tip="Check conversation in the database and inform support team (create Fogbugz case manually if needed).",
                )
            )
    else:
        assert not is_first_message  # nosec
        _logger.info(
            "Support settings available, but this is NOT the first message, so we need to reopen a FogBugz case. Conversation ID: %s",
            conversation.conversation_id,
        )
        assert product.support_assigned_fogbugz_project_id  # nosec
        assert product.support_assigned_fogbugz_person_id  # nosec
        assert conversation.fogbugz_case_id  # nosec

        try:
            await _conversation_service.reopen_fogbugz_case_for_support_conversation(
                app,
                case_id=conversation.fogbugz_case_id,
                conversation_url=_conversation_url,
                product_support_assigned_fogbugz_person_id=f"{product.support_assigned_fogbugz_person_id}",
            )
        except Exception as err:  # pylint: disable=broad-except
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Failed to reopen support request FogBugz case for conversation {conversation.conversation_id}",
                    error=err,
                    error_context={
                        "conversation": conversation,
                        "user_id": user_id,
                        "fogbugz_url": str(fogbugz_settings_or_none.FOGBUGZ_URL),
                    },
                    tip="Check conversation in the database and corresponding Fogbugz case",
                )
            )

    if (
        product.support_chatbot_user_id
        and conversation.type == ConversationType.SUPPORT
        and conversation_user_type == ConversationUserType.REGULAR_USER
    ):
        # If enabled, ask Chatbot to analyze the message history and respond
        await _trigger_chatbot_processing(
            app,
            conversation=conversation,
            last_message_id=message.message_id,
        )

    return message


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
    product_name: ProductName,
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
            recipients=await _conversation_service.get_recipients_from_project(
                app, project_id
            ),
            project_id=project_id,
            conversation_message=updated_message,
        )
    else:
        _conversation = await _conversation_service.get_conversation(
            app, conversation_id=conversation_id
        )
        _conversation_creator_user = await users_service.get_user_id_from_gid(
            app, primary_gid=_conversation.user_group_id
        )
        _product_group_users = await _get_recipients_from_product_support_group(
            app, product_name=product_name
        )
        await notify_conversation_message_updated(
            app,
            recipients=_product_group_users | {_conversation_creator_user},
            project_id=None,
            conversation_message=updated_message,
        )

    return updated_message


async def delete_message(
    app: web.Application,
    *,
    product_name: ProductName,
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
            recipients=await _conversation_service.get_recipients_from_project(
                app, project_id
            ),
            user_group_id=_user_group_id,
            project_id=project_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    else:
        _conversation = await _conversation_service.get_conversation(
            app, conversation_id=conversation_id
        )
        _conversation_creator_user = await users_service.get_user_id_from_gid(
            app, primary_gid=_conversation.user_group_id
        )
        _product_group_users = await _get_recipients_from_product_support_group(
            app, product_name=product_name
        )
        await notify_conversation_message_deleted(
            app,
            recipients=_product_group_users | {_conversation_creator_user},
            user_group_id=_user_group_id,
            project_id=None,
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
    # ordering
    order_by: OrderBy | None = None,
) -> tuple[PageTotalCount, list[ConversationMessageGetDB]]:
    return await _conversation_message_repository.list_(
        app,
        conversation_id=conversation_id,
        offset=offset,
        limit=limit,
        order_by=order_by
        or OrderBy(
            field=IDStr("created"), direction=OrderDirection.DESC
        ),  # NOTE: Message should be ordered by creation date (latest first)
    )
