from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionId,
    CreditTransactionStatus,
)
from models_library.wallets import WalletID
from servicelib.rabbitmq import RabbitMQClient

from ..api.rest.dependencies import get_repository
from ..models.credit_transactions import CreditTransactionCreate
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .modules.rabbitmq import get_rabbitmq_client_from_request
from .utils import sum_credit_transactions_and_publish_to_rabbitmq


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
        pricing_unit_id=None,
        pricing_unit_cost_id=None,
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

    await sum_credit_transactions_and_publish_to_rabbitmq(
        resource_tracker_repo,
        rabbitmq_client,
        credit_transaction_create_body.product_name,
        credit_transaction_create_body.wallet_id,
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
