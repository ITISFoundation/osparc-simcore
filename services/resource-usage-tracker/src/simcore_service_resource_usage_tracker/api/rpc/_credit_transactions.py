from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import CreditTransactionStatus
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter

from ...services import credit_transactions

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def get_wallet_total_credits(
    app: FastAPI,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    # internal filters
    transaction_status: CreditTransactionStatus | None = None,
    project_id: ProjectID | None = None,
) -> WalletTotalCredits:
    return await credit_transactions.sum_credit_transactions_by_product_and_wallet(
        db_engine=app.state.engine,
        product_name=product_name,
        wallet_id=wallet_id,
        transaction_status=transaction_status,
        project_id=project_id,
    )


@router.expose(reraise_if_error_type=())
async def pay_project_debt(
    app: FastAPI,
    *,
    project_id: ProjectID,
    current_wallet_transaction: CreditTransactionCreateBody,
    new_wallet_transaction: CreditTransactionCreateBody,
) -> None:
    return await credit_transactions.pay_project_debt(
        db_engine=app.state.engine,
        rabbitmq_client=app.state.rabbitmq_client,
        project_id=project_id,
        current_wallet_transaction=current_wallet_transaction,
        new_wallet_transaction=new_wallet_transaction,
    )
