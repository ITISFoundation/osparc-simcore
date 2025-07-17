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
    service_runs,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..users import users_service
from ..wallets import _api as wallets_service
from ._projects_repository_legacy import ProjectDBAPI
from .exceptions import (
    ProjectInDebtCanNotChangeWalletError,
    ProjectInDebtCanNotOpenError,
    ProjectWalletPendingTransactionError,
)


async def get_project_wallet(app, project_id: ProjectID):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    wallet_db: WalletDB | None = await db.get_project_wallet(project_uuid=project_id)
    wallet: WalletGet | None = (
        WalletGet(**wallet_db.model_dump()) if wallet_db else None
    )
    return wallet


async def check_project_financial_status(
    app, *, project_id: ProjectID, product_name: ProductName
):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    current_project_wallet = await db.get_project_wallet(project_uuid=project_id)
    rpc_client = get_rabbitmq_rpc_client(app)

    if current_project_wallet:
        # Do not allow to open project if the project connected wallet is in DEBT!
        project_wallet_credits_in_debt = (
            await credit_transactions.get_project_wallet_total_credits(
                rpc_client,
                product_name=product_name,
                wallet_id=current_project_wallet.wallet_id,
                project_id=project_id,
                transaction_status=CreditTransactionStatus.IN_DEBT,
            )
        )
        if project_wallet_credits_in_debt.available_osparc_credits < 0:
            raise ProjectInDebtCanNotOpenError(
                debt_amount=project_wallet_credits_in_debt.available_osparc_credits,
                wallet_id=current_project_wallet.wallet_id,
            )


async def connect_wallet_to_project(
    app,
    *,
    product_name: ProductName,
    project_id: ProjectID,
    user_id: UserID,
    wallet_id: WalletID,
) -> WalletGet:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    # ensure the wallet can be used by the user
    wallet: WalletGet = await wallets_service.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    current_project_wallet = await db.get_project_wallet(project_uuid=project_id)
    rpc_client = get_rabbitmq_rpc_client(app)

    if current_project_wallet:
        # Do not allow to change wallet if the project connected wallet is in DEBT!
        project_wallet_credits_in_debt = (
            await credit_transactions.get_project_wallet_total_credits(
                rpc_client,
                product_name=product_name,
                wallet_id=current_project_wallet.wallet_id,
                project_id=project_id,
                transaction_status=CreditTransactionStatus.IN_DEBT,
            )
        )
        if project_wallet_credits_in_debt.available_osparc_credits < 0:
            raise ProjectInDebtCanNotChangeWalletError(
                debt_amount=project_wallet_credits_in_debt.available_osparc_credits,
                wallet_id=current_project_wallet.wallet_id,
            )

        # Do not allow to change wallet if the project has transaction in PENDING!
        project_service_runs_in_progress = await service_runs.get_service_run_page(
            rpc_client,
            user_id=user_id,
            product_name=product_name,
            wallet_id=current_project_wallet.wallet_id,
            access_all_wallet_usage=True,
            transaction_status=CreditTransactionStatus.PENDING,
            project_id=project_id,
            offset=0,
            limit=1,
        )
        if project_service_runs_in_progress.total > 0:
            raise ProjectWalletPendingTransactionError

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
    - debt_amount: The amount of debt to be payed (e.g., -100 credits). Needs to be negative.

    Process:
    1. Transfer the specified debt amount from Wallet B to Wallet A.
    2. Update the project's debt status (this unblocks the project).

    Outcome:
    The project's debt is paid, Wallet A is credited, and Wallet B is debited.
    """

    assert current_wallet_id != new_wallet_id  # nosec

    # ensure the wallets can be used by the user
    new_wallet: WalletGet = await wallets_service.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=new_wallet_id,
        product_name=product_name,
    )
    current_wallet: WalletGet = await wallets_service.get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=current_wallet_id,
        product_name=product_name,
    )

    user = await users_service.get_user(app, user_id=user_id)

    # Transfer credits from the source wallet to the connected wallet
    rpc_client = get_rabbitmq_rpc_client(app)
    _created_at = datetime.now(tz=UTC)

    new_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=new_wallet_id,
        wallet_name=new_wallet.name,
        user_id=user_id,
        user_email=user["email"],
        osparc_credits=debt_amount,  # <-- Negative number
        payment_transaction_id=f"Payment transaction from wallet {current_wallet_id} to wallet {new_wallet_id}. Project id {project_id}.",
        created_at=_created_at,
    )

    current_wallet_transaction = CreditTransactionCreateBody(
        product_name=product_name,
        wallet_id=current_wallet_id,
        wallet_name=current_wallet.name,
        user_id=user_id,
        user_email=user["email"],
        osparc_credits=-debt_amount,  # <-- Positive number
        payment_transaction_id=f"Payment transaction from wallet {new_wallet_id} to wallet {current_wallet_id}. Project id {project_id}.",
        created_at=_created_at,
    )

    await credit_transactions.pay_project_debt(
        rpc_client,
        project_id=project_id,
        current_wallet_transaction=current_wallet_transaction,
        new_wallet_transaction=new_wallet_transaction,
    )
