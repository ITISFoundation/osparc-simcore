from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.rabbitmq_messages import WalletCreditsMessage
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionId,
    CreditTransactionStatus,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel
from servicelib.rabbitmq import RabbitMQClient

from ..api.dependencies import get_repository
from ..models.resource_tracker_credit_transactions import CreditTransactionCreate
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository
from ..modules.rabbitmq import get_rabbitmq_client_from_request


class CreditTransactionCreateBody(BaseModel):
    product_name: ProductName
    wallet_id: WalletID
    wallet_name: str
    user_id: UserID
    user_email: str
    osparc_credits: Decimal
    payment_transaction_id: str
    created_at: datetime


async def _sum_credit_transactions_and_publish_to_rabbitmq(
    resource_tracker_repo: ResourceTrackerRepository,
    credit_transaction_create_body: CreditTransactionCreateBody,
    wallet_id: WalletID,
    rabbitmq_client: RabbitMQClient,
):
    wallet_total_credits = (
        await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
            credit_transaction_create_body.product_name,
            credit_transaction_create_body.wallet_id,
        )
    )
    publish_message = WalletCreditsMessage.construct(
        wallet_id=wallet_id,
        created_at=datetime.now(tz=timezone.utc),
        credits=wallet_total_credits,
    )
    await rabbitmq_client.publish(publish_message.channel_name, publish_message)


async def create_credit_transaction(
    credit_transaction_create_body: CreditTransactionCreateBody,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
    rabbitmq_client: Annotated[
        RabbitMQClient, Depends(get_rabbitmq_client_from_request)
    ],
) -> CreditTransactionId:
    transaction_create = CreditTransactionCreate(
        product_name=credit_transaction_create_body.product_name,
        wallet_id=credit_transaction_create_body.wallet_id,
        wallet_name=credit_transaction_create_body.wallet_name,
        pricing_plan_id=None,
        pricing_detail_id=None,
        user_id=credit_transaction_create_body.user_id,
        user_email=credit_transaction_create_body.user_email,
        osparc_credits=credit_transaction_create_body.osparc_credits,
        transaction_status=CreditTransactionStatus.BILLED,
        transaction_classification=CreditClassification.ADD_WALLET_TOP_UP,
        service_run_id=None,
        payment_transaction_id=credit_transaction_create_body.payment_transaction_id,
        created_at=credit_transaction_create_body.created_at,
        last_heartbeat_at=credit_transaction_create_body.created_at,
    )
    transaction_id = await resource_tracker_repo.create_credit_transaction(
        transaction_create
    )

    await _sum_credit_transactions_and_publish_to_rabbitmq(
        resource_tracker_repo,
        credit_transaction_create_body,
        credit_transaction_create_body.wallet_id,
        rabbitmq_client,
    )

    return transaction_id


async def sum_credit_transactions_by_product_and_wallet(
    product_name: ProductName,
    wallet_id: WalletID,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> WalletTotalCredits:
    return await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
        product_name, wallet_id
    )
