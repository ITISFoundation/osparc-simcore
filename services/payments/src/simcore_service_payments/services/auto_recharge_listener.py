import functools
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
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


async def _unsubscribe_consumer(app, queue_name: QueueName, consumer_tag: ConsumerTag) -> None:
    with log_context(_logger, logging.INFO, msg="Unsubscribing from rabbitmq queue"):
        rabbit_client = get_rabbitmq_client(app)
        await rabbit_client.unsubscribe_consumer(queue_name, consumer_tag)


def configure_auto_recharge_listener(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _auto_recharge_listener_lifespan(app: FastAPI) -> AsyncIterator[State]:
        app.state.auto_recharge_rabbitmq_consumer = None
        try:
            app.state.auto_recharge_rabbitmq_consumer = await _subscribe_to_rabbitmq(app)
            yield {}
        finally:
            consumer = app.state.auto_recharge_rabbitmq_consumer
            if consumer and app.state.rabbitmq_client:
                assert isinstance(consumer, tuple)  # nosec
                # NOTE: We want to have persistent queue, therefore we will unsubscribe only consumer
                await _unsubscribe_consumer(app, *consumer)
            app.state.auto_recharge_rabbitmq_consumer = None

    app_lifespan.add(_auto_recharge_listener_lifespan)
