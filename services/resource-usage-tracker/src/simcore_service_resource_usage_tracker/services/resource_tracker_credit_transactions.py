from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionId,
    CreditTransactionStatus,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel

from ..api.dependencies import get_repository
from ..models.resource_tracker_credit_transactions import CreditTransactionCreate
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository


class CreditTransactionCreateBody(BaseModel):
    product_name: ProductName
    wallet_id: WalletID
    wallet_name: str
    user_id: UserID
    user_email: str
    osparc_credits: Decimal
    payment_transaction_id: str
    created_at: datetime


async def create_credit_transaction(
    credit_transaction_create_body: CreditTransactionCreateBody,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
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

    # NOTE: Implement fire and forget mechanism
    wallet_total_credits = (
        await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
            credit_transaction_create_body.product_name,
            credit_transaction_create_body.wallet_id,
        )
    )
    assert wallet_total_credits  # nosec
    # NOTE: Publish wallet total credits to RabbitMQ

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
    # NOTE: Publish wallet total credits to RabbitMQ
