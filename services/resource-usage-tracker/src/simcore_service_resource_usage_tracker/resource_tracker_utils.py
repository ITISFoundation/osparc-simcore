import logging
from datetime import datetime, timezone

from models_library.products import ProductName
from models_library.rabbitmq_messages import WalletCreditsMessage
from models_library.wallets import WalletID
from servicelib.rabbitmq import RabbitMQClient

from .modules.db.repositories.resource_tracker import ResourceTrackerRepository

_logger = logging.getLogger(__name__)


def make_negative(n):
    return -abs(n)


async def sum_credit_transactions_and_publish_to_rabbitmq(
    resource_tracker_repo: ResourceTrackerRepository,
    rabbitmq_client: RabbitMQClient,
    product_name: ProductName,
    wallet_id: WalletID,
):
    wallet_total_credits = (
        await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
            product_name,
            wallet_id,
        )
    )
    publish_message = WalletCreditsMessage.construct(
        wallet_id=wallet_id,
        created_at=datetime.now(tz=timezone.utc),
        credits=wallet_total_credits.available_osparc_credits,
    )
    await rabbitmq_client.publish(publish_message.channel_name, publish_message)
