import functools
import logging
from collections.abc import AsyncIterator
from typing import Final

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.conversations import ConversationMessageType, ConversationUserType
from models_library.rabbitmq_messages import WebserverChatbotRabbitMessage
from models_library.rest_ordering import OrderBy, OrderDirection
from pydantic import TypeAdapter
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient

from ..conversations import conversations_service
from ..conversations.errors import ConversationErrorNotFoundError
from ..products import products_service
from ..rabbitmq import get_rabbitmq_client
from ..users import users_service
from ._client import Message
from .chatbot_service import get_chatbot_rest_client
from .exceptions import InvalidUserInConversationError

_logger = logging.getLogger(__name__)


_RABBITMQ_WEBSERVER_CHATBOT_CONSUMER_APPKEY: Final = web.AppKey(
    "RABBITMQ_WEBSERVER_CHATBOT_CONSUMER", str
)

_CHATBOT_PROCESS_MESSAGE_TTL_IN_MS = 2 * 60 * 60 * 1000  # 2 hours


async def _process_chatbot_trigger_message(app: web.Application, data: bytes) -> bool:
    rabbit_message = TypeAdapter(WebserverChatbotRabbitMessage).validate_json(data)
    assert app  # nosec

    with log_context(
        _logger,
        logging.DEBUG,
        msg=f"Processing chatbot trigger message for conversation ID {rabbit_message.conversation.conversation_id}",
    ):
        _product_name = rabbit_message.conversation.product_name
        _user_primary_gid = rabbit_message.conversation.user_group_id
        _product = products_service.get_product(app, product_name=_product_name)
        _user_id = await users_service.get_user_id_from_gid(
            app=app, primary_gid=_user_primary_gid
        )
        _user_info = await users_service.get_user_name_and_email(
            app=app, user_id=_user_id
        )

        if _product.support_chatbot_user_id is None:
            _logger.error(
                "Product %s does not have support_chatbot_user_id configured, cannot process chatbot message. (This should not happen)",
                _product_name,
            )
            return True  # return true to avoid re-processing
        _chatbot_primary_gid = await users_service.get_user_primary_group_id(
            app=app, user_id=_product.support_chatbot_user_id
        )

        # Get last 20 messages for the conversation ID
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Listed messages for conversation ID {rabbit_message.conversation.conversation_id}",
        ):
            _, messages_in_db = (
                await conversations_service.list_messages_for_conversation(
                    app=app,
                    conversation_id=rabbit_message.conversation.conversation_id,
                    offset=0,
                    limit=20,
                    order_by=OrderBy(
                        field=IDStr("created"), direction=OrderDirection.DESC
                    ),
                )
            )

        def _get_role(message_group_id):
            if message_group_id == _user_primary_gid:
                return "user"
            elif message_group_id == _chatbot_primary_gid:
                return "assistant"
            else:
                raise InvalidUserInConversationError(
                    primary_group_id=message_group_id,
                    conversation_id=rabbit_message.conversation.conversation_id,
                )

        messages = [
            Message(role=_get_role(msg.user_group_id), content=msg.content)
            for msg in messages_in_db
        ]
        context_message = Message(
            role="developer",
            content=(
                "Here is the context within which the user's question is asked. "
                f"username: '{_user_info.name}' "
                f"product: '{_product_name}' "
                "Make your answers concise, to the point and refer to the user by their username."
            ),
        )
        messages.append(context_message)

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
                    user_id=_product.support_chatbot_user_id,
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
