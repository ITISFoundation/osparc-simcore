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
from .chatbot_service import get_chatbot_rest_client

_logger = logging.getLogger(__name__)


_RABBITMQ_WEBSERVER_CHATBOT_CONSUMER_APPKEY: Final = web.AppKey(
    "RABBITMQ_WEBSERVER_CHATBOT_CONSUMER", str
)

_CHATBOT_PROCESS_MESSAGE_TTL_IN_MS = 2 * 60 * 60 * 1000  # 2 hours


async def _process_chatbot_trigger_message(app: web.Application, data: bytes) -> bool:
    rabbit_message = TypeAdapter(WebserverChatbotRabbitMessage).validate_json(data)
    assert app  # nosec

    _logger.info(
        "Processing chatbot trigger message for conversation ID=%s",
        rabbit_message.conversation.conversation_id,
    )

    _product_name = rabbit_message.conversation.product_name
    _product = products_service.get_product(app, product_name=_product_name)

    if _product.support_chatbot_user_id is None:
        _logger.error(
            "Product %s does not have support_chatbot_user_id configured, cannot process chatbot message. (This should not happen)",
            _product_name,
        )
        return True  # return true to avoid re-processing

    # Get last 20 messages for the conversation ID
    _, messages = await conversations_service.list_messages_for_conversation(
        app=app,
        conversation_id=rabbit_message.conversation.conversation_id,
        offset=0,
        limit=20,
        order_by=OrderBy(field=IDStr("created"), direction=OrderDirection.DESC),
    )

    _question_for_chatbot = ""
    for inx, msg in enumerate(messages):
        if inx == 0:
            # Make last message stand out as the question
            _question_for_chatbot += (
                "User last message: \n"
                f"{msg.content.strip()} \n\n"
                "Previous messages in the conversation: \n"
            )
        else:
            _question_for_chatbot += f"{msg.content.strip()}\n"

    # Talk to the chatbot service
    chatbot_client = get_chatbot_rest_client(app)
    chat_response = await chatbot_client.ask_question(_question_for_chatbot)

    try:
        await conversations_service.create_support_message(
            app=app,
            product_name=rabbit_message.conversation.product_name,
            user_id=_product.support_chatbot_user_id,
            conversation_user_type=ConversationUserType.CHATBOT_USER,
            conversation=rabbit_message.conversation,
            content=chat_response.answer,
            type_=ConversationMessageType.MESSAGE,
        )
    except ConversationErrorNotFoundError:
        _logger.warning(
            "Can not create a support message as conversation %s was not found",
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
