from datetime import UTC, datetime
from decimal import Decimal

from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
)
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import CreditTransactionStatus
from models_library.users import UserID
from models_library.wallets import WalletDB, WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    credit_transactions,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..users import api as users_api
from ..wallets import _api as wallets_api
from .db import ProjectDBAPI


async def get_project_wallet(app, project_id: ProjectID):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    wallet_db: WalletDB | None = await db.get_project_wallet(project_uuid=project_id)
    wallet: WalletGet | None = (
        WalletGet(**wallet_db.model_dump()) if wallet_db else None
    )
    return wallet


async def connect_wallet_to_project(
    app,
    *,
    product_name: ProductName,
    project_id: ProjectID,
    user_id: UserID,
    wallet_id: WalletID,
) -> WalletGet:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    project_wallet = await db.get_project_wallet(project_uuid=project_id)

    if project_wallet:
        # NOTE: Do not allow to change wallet if the project is in DEBT!
        rpc_client = get_rabbitmq_rpc_client(app)
        project_wallet_credits = await credit_transactions.get_wallet_total_credits(
            rpc_client,
            product_name=product_name,
            wallet_id=project_wallet.wallet_id,
            project_id=project_id,
            transaction_status=CreditTransactionStatus.IN_DEBT,
        )
        if project_wallet_credits.available_osparc_credits > 0:
            msg = f"Current Project Wallet {project_wallet.wallet_id} is in DEBT"
            raise ValueError(msg)

    # ensure the wallet can be used by the user
    wallet: WalletGet = await wallets_api.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    # Allow changing the wallet only if there are no pending transactions within the project.
    # TODO: MATUS: check pending transactions

    await db.connect_wallet_to_project(project_uuid=project_id, wallet_id=wallet_id)
    return wallet


async def pay_debt_with_different_wallet(
    app,
    *,
    product_name: ProductName,
    project_id: ProjectID,
    user_id: UserID,
    current_wallet_id: WalletID,
    new_wallet_id: WalletID,
    debt_amount: Decimal,
) -> None:
    """
    Handles the repayment of a project's debt using a different wallet.

    Example scenario:
    - A project has a debt of -100 credits.
    - Wallet A is the current wallet connected to the project and has -200 credits.
    - The user wants to pay the project's debt using Wallet B, which has 500 credits.

    Parameters:
    - current_wallet_id: ID of Wallet A (the wallet currently linked to the project).
    - new_wallet_id: ID of Wallet B (the wallet the user wants to use to pay the debt).
    - debt_amount: The amount to be transferred (e.g., 100 credits).

    Process:
    1. Transfer the specified debt amount (100 credits) from Wallet B to Wallet A.
    2. Update the project's debt status (e.g., unblock the project).

    Outcome:
    The project's debt is paid, Wallet A is credited, and Wallet B is debited.
    """

    assert current_wallet_id != new_wallet_id  # nosec

    # ensure the wallets can be used by the user
    new_wallet: WalletGet = await wallets_api.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=new_wallet_id,
        product_name=product_name,
    )
    current_wallet: WalletGet = await wallets_api.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=current_wallet_id,
        product_name=product_name,
    )

    user = await users_api.get_user(app, user_id=user_id)

    # Transfer credits from the source wallet to the connected wallet
    rpc_client = get_rabbitmq_rpc_client(app)
    _created_at = datetime.now(tz=UTC)

    new_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=new_wallet_id,
        wallet_name=new_wallet.name,
        user_id=user_id,
        user_email=user["email"],
        osparc_credits=-debt_amount,  # <-- Negative number
        payment_transaction_id=f"Payment transaction from wallet {current_wallet_id} to wallet {new_wallet_id}",
        created_at=_created_at,
    )

    current_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=current_wallet_id,
        wallet_name=current_wallet.name,
        user_id=user_id,
        user_email=user["email"],
        osparc_credits=debt_amount,  # <-- Positive number
        payment_transaction_id=f"Payment transaction from wallet {new_wallet_id} to wallet {current_wallet_id}",
        created_at=_created_at,
    )

    await credit_transactions.pay_project_debt(
        rpc_client,
        project_id=project_id,
        current_wallet_transaction=current_wallet_transaction,
        new_wallet_transaction=new_wallet_transaction,
    )
