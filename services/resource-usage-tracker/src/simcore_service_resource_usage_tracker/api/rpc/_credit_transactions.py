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

from ...services import credit_transactions, service_runs

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def get_wallet_total_credits(
    app: FastAPI,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
) -> WalletTotalCredits:
    return await credit_transactions.sum_wallet_credits(
        db_engine=app.state.engine,
        product_name=product_name,
        wallet_id=wallet_id,
    )


@router.expose(reraise_if_error_type=())
async def get_project_wallet_total_credits(
    app: FastAPI,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    project_id: ProjectID,
    transaction_status: CreditTransactionStatus | None = None,
) -> WalletTotalCredits:
    return await service_runs.sum_project_wallet_total_credits(
        db_engine=app.state.engine,
        product_name=product_name,
        wallet_id=wallet_id,
        project_id=project_id,
        transaction_status=transaction_status,
    )


@router.expose(reraise_if_error_type=(ValueError,))
async def pay_project_debt(
    app: FastAPI,
    *,
    project_id: ProjectID,
    current_wallet_transaction: CreditTransactionCreateBody,
    new_wallet_transaction: CreditTransactionCreateBody,
) -> None:
    await credit_transactions.pay_project_debt(
        db_engine=app.state.engine,
        rabbitmq_client=app.state.rabbitmq_client,
        rut_fire_and_forget_tasks=app.state.rut_fire_and_forget_tasks,
        project_id=project_id,
        current_wallet_transaction=current_wallet_transaction,
        new_wallet_transaction=new_wallet_transaction,
    )
