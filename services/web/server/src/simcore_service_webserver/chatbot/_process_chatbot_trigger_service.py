import functools
import logging
from collections.abc import AsyncIterator
from typing import Final, Literal, NamedTuple

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.conversations import ConversationMessageType, ConversationUserType
from models_library.groups import GroupID
from models_library.rabbitmq_messages import WebserverChatbotRabbitMessage
from models_library.rest_ordering import OrderBy, OrderDirection
from pydantic import TypeAdapter
from servicelib.logging_utils import log_catch, log_context, log_decorator
from servicelib.rabbitmq import RabbitMQClient

from ..conversations import conversations_service
from ..conversations.errors import ConversationErrorNotFoundError
from ..groups.api import list_group_members
from ..products import products_service
from ..rabbitmq import get_rabbitmq_client
from ..users import users_service
from ._client import Message
from .chatbot_service import get_chatbot_rest_client

_logger = logging.getLogger(__name__)


_RABBITMQ_WEBSERVER_CHATBOT_CONSUMER_APPKEY: Final = web.AppKey("RABBITMQ_WEBSERVER_CHATBOT_CONSUMER", str)

_CHATBOT_PROCESS_MESSAGE_TTL_IN_MS = 2 * 60 * 60 * 1000  # 2 hours


class _Role(NamedTuple):
    role: Literal["user", "assistant", "developer"]
    name: str | None = None


_SUPPORT_ROLE_NAME: Final[str] = "support-team-member"

_CHATBOT_INSTRUCTION_MESSAGE: Final[str] = """
    This conversation takes place in the context of the {product} product.
    Only answer questions related to this product.
    The user '{support_role_name}' is a support team member and is
    assisting users of the {product} product with their inquiries. Help the user by
    providing answers to their questions. Make your answers concise and to the point.
    Address users by their name. Be friendly and accommodating.
    """


async def _get_role(
    *,
    app: web.Application,
    message_gid: GroupID,
    chatbot_primary_gid: GroupID,
    support_group_primary_gids: set[GroupID],
) -> _Role:
    if message_gid == chatbot_primary_gid:
        return _Role(role="assistant")
    if message_gid in support_group_primary_gids:
        return _Role(role="user", name=_SUPPORT_ROLE_NAME)
    user_id = await users_service.get_user_id_from_gid(app=app, primary_gid=message_gid)
    user_full_name = await users_service.get_user_fullname(app=app, user_id=user_id)
    return _Role(role="user", name=user_full_name["first_name"])


@log_decorator(_logger, logging.DEBUG)
async def _process_chatbot_trigger_message(app: web.Application, data: bytes) -> bool:
    rabbit_message = TypeAdapter(WebserverChatbotRabbitMessage).validate_json(data)
    assert app  # nosec

    with log_catch(logger=_logger, reraise=False):
        product_name = rabbit_message.conversation.product_name
        product = products_service.get_product(app, product_name=product_name)

        if product.support_chatbot_user_id is None:
            error_msg = (
                f"Product {product_name} does not have support_chatbot_user_id configured, "
                "cannot process chatbot message. (This should not happen)"
            )
            _logger.error(error_msg)
            return True  # return true to avoid re-processing
        support_group_primary_gids = set()
        if product.support_standard_group_id is not None:
            support_group_primary_gids = {
                elm.primary_gid for elm in await list_group_members(app, product.support_standard_group_id)
            }

        chatbot_primary_gid = await users_service.get_user_primary_group_id(
            app=app, user_id=product.support_chatbot_user_id
        )

        # Get last 20 messages for the conversation ID
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Listed messages for conversation ID {rabbit_message.conversation.conversation_id}",
        ):
            _, messages_in_db = await conversations_service.list_messages_for_conversation(
                app=app,
                conversation_id=rabbit_message.conversation.conversation_id,
                offset=0,
                limit=20,
                order_by=OrderBy(field=IDStr("created"), direction=OrderDirection.DESC),
            )
            messages_in_db.reverse()  # to have them in ascending order

        messages = [
            Message(
                role="developer",
                content=_CHATBOT_INSTRUCTION_MESSAGE.format(
                    product=product_name,
                    support_role_name=_SUPPORT_ROLE_NAME,
                ),
            )
        ]
        for msg in messages_in_db:
            role = await _get_role(
                app=app,
                message_gid=msg.user_group_id,
                chatbot_primary_gid=chatbot_primary_gid,
                support_group_primary_gids=support_group_primary_gids,
            )
            messages.append(Message(role=role.role, name=role.name, content=msg.content))

        # Talk to the chatbot service
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Asking question from chatbot conversation ID {rabbit_message.conversation.conversation_id}",
        ):
            chatbot_client = get_chatbot_rest_client(app)
            response_message = await chatbot_client.send(messages)

        try:
            with log_context(
                _logger,
                logging.DEBUG,
                msg=f"Creating support message in conversation ID {rabbit_message.conversation.conversation_id}",
            ):
                await conversations_service.create_support_message(
                    app=app,
                    product_name=rabbit_message.conversation.product_name,
                    user_id=product.support_chatbot_user_id,
                    conversation_user_type=ConversationUserType.CHATBOT_USER,
                    conversation=rabbit_message.conversation,
                    content=response_message.content,
                    type_=ConversationMessageType.MESSAGE,
                )
        except ConversationErrorNotFoundError:
            _logger.warning(
                "Can not create a support message as conversation %s was not found",
                rabbit_message.conversation.conversation_id,
            )

        _logger.debug(
            "Process_chatbot_trigger_message all good, returning True for conversation ID %s",
            rabbit_message.conversation.conversation_id,
        )
        return True


async def _subscribe_to_rabbitmq(app) -> str:
    with log_context(
        _logger,
        logging.INFO,
        msg=f"Subscribing to {WebserverChatbotRabbitMessage.get_channel_name()} channel",
    ):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue, _ = await rabbit_client.subscribe(
            WebserverChatbotRabbitMessage.get_channel_name(),
            message_handler=functools.partial(_process_chatbot_trigger_message, app),
            exclusive_queue=False,
            message_ttl=_CHATBOT_PROCESS_MESSAGE_TTL_IN_MS,
        )
        return subscribed_queue


async def _unsubscribe_from_rabbitmq(app) -> None:
    assert app  # nosec


async def on_cleanup_ctx_rabbitmq_consumer(
    app: web.Application,
) -> AsyncIterator[None]:
    app[_RABBITMQ_WEBSERVER_CHATBOT_CONSUMER_APPKEY] = await _subscribe_to_rabbitmq(app)

    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
