import logging

from aiohttp import web
from models_library.rabbitmq_messages import WalletCreditsMessage
from models_library.wallets import WalletID
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient

from ..rabbitmq import get_rabbitmq_client
from ._rabbitmq_exclusive_queue_consumers import (
    APP_WALLET_SUBSCRIPTION_LOCK_KEY,
    APP_WALLET_SUBSCRIPTIONS_KEY,
)

_logger = logging.getLogger(__name__)


async def subscribe(app: web.Application, wallet_id: WalletID) -> None:

    async with app[APP_WALLET_SUBSCRIPTION_LOCK_KEY]:
        counter = app[APP_WALLET_SUBSCRIPTIONS_KEY][wallet_id]
        app[APP_WALLET_SUBSCRIPTIONS_KEY][wallet_id] += 1

        if counter == 0:  # First subscriber
            rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
            await rabbit_client.add_topics(
                WalletCreditsMessage.get_channel_name(), topics=[f"{wallet_id}"]
            )


async def unsubscribe(app: web.Application, wallet_id: WalletID) -> None:

    async with app[APP_WALLET_SUBSCRIPTION_LOCK_KEY]:
        counter = app[APP_WALLET_SUBSCRIPTIONS_KEY].get(wallet_id, 0)
        if counter > 0:
            app[APP_WALLET_SUBSCRIPTIONS_KEY][wallet_id] -= 1

            if counter == 1:  # Last subscriber
                rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
                with log_catch(_logger, reraise=False):
                    await rabbit_client.remove_topics(
                        WalletCreditsMessage.get_channel_name(), topics=[f"{wallet_id}"]
                    )
