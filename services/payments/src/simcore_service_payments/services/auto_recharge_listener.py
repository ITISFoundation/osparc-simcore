import functools
import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import WalletCreditsMessage
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import ConsumerTag, QueueName

from .auto_recharge_process_message import process_message
from .rabbitmq import get_rabbitmq_client

_logger = logging.getLogger(__name__)


async def _subscribe_to_rabbitmq(app) -> tuple[QueueName, ConsumerTag]:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channel"):
        rabbit_client = get_rabbitmq_client(app)
        return await rabbit_client.subscribe(
            WalletCreditsMessage.get_channel_name(),
            message_handler=functools.partial(process_message, app),
            exclusive_queue=False,
            topics=["#"],
        )


async def _unsubscribe_consumer(
    app, queue_name: QueueName, consumer_tag: ConsumerTag
) -> None:
    with log_context(_logger, logging.INFO, msg="Unsubscribing from rabbitmq queue"):
        rabbit_client = get_rabbitmq_client(app)
        await rabbit_client.unsubscribe_consumer(queue_name, consumer_tag)


def setup_auto_recharge_listener(app: FastAPI):
    async def _on_startup() -> None:
        app.state.auto_recharge_rabbitmq_consumer = await _subscribe_to_rabbitmq(app)

    async def _on_shutdown() -> None:
        assert app.state.auto_recharge_rabbitmq_consumer  # nosec
        assert isinstance(app.state.auto_recharge_rabbitmq_consumer, tuple)  # nosec
        if app.state.rabbitmq_client:
            # NOTE: We want to have persistent queue, therefore we will unsubscribe only consumer
            await _unsubscribe_consumer(app, *app.state.auto_recharge_rabbitmq_consumer)
        app.state.auto_recharge_rabbitmq_consumer = None

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
