import functools
import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import WalletCreditsMessage
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient

from .auto_recharge_process_message import process_message
from .rabbitmq import get_rabbitmq_client

_logger = logging.getLogger(__name__)


async def _subscribe_to_rabbitmq(app) -> str:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channel"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue: str = await rabbit_client.subscribe(
            WalletCreditsMessage.get_channel_name(),
            message_handler=functools.partial(process_message, app),
            exclusive_queue=False,
            topics=["#"],
        )
        return subscribed_queue


def setup_auto_recharge_listener(app: FastAPI) -> None:
    async def _on_startup() -> None:
        app.state.auto_recharge_rabbitmq_consumer = await _subscribe_to_rabbitmq(app)

    async def _on_shutdown() -> None:
        # NOTE: We want to have persistent queue, therefore we will not unsubscribe
        ...

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
