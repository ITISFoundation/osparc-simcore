from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionId,
    CreditTransactionStatus,
)
from models_library.wallets import WalletID
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    WalletTransactionError,
)
from servicelib.utils import fire_and_forget_task
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from ..models.credit_transactions import CreditTransactionCreate
from ..services.modules.db import service_runs_db
from .modules.db import credit_transactions_db
from .modules.rabbitmq import get_rabbitmq_client_from_request
from .utils import sum_credit_transactions_and_publish_to_rabbitmq


async def create_credit_transaction(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    rabbitmq_client: Annotated[
        RabbitMQClient, Depends(get_rabbitmq_client_from_request)
    ],
    credit_transaction_create_body: CreditTransactionCreateBody,
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
        licensed_item_purchase_id=None,
        created_at=credit_transaction_create_body.created_at,
        last_heartbeat_at=credit_transaction_create_body.created_at,
    )
    async with transaction_context(db_engine) as conn:
        transaction_id = await credit_transactions_db.create_credit_transaction(
            db_engine, connection=conn, data=transaction_create
        )

        wallet_total_credits = await sum_credit_transactions_and_publish_to_rabbitmq(
            db_engine,
            connection=conn,
            rabbitmq_client=rabbitmq_client,
            product_name=credit_transaction_create_body.product_name,
            wallet_id=credit_transaction_create_body.wallet_id,
        )
        if wallet_total_credits.available_osparc_credits >= 0:
            # Change status from `IN_DEBT` to `BILLED`
            await credit_transactions_db.batch_update_credit_transaction_status_for_in_debt_transactions(
                db_engine,
                connection=conn,
                project_id=None,
                wallet_id=credit_transaction_create_body.wallet_id,
                transaction_status=CreditTransactionStatus.BILLED,
            )

        return transaction_id


async def sum_wallet_credits(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    wallet_id: WalletID,
) -> WalletTotalCredits:
    return await credit_transactions_db.sum_wallet_credits(
        db_engine,
        product_name=product_name,
        wallet_id=wallet_id,
    )


async def pay_project_debt(
    db_engine: AsyncEngine,
    rabbitmq_client: RabbitMQClient,
    rut_fire_and_forget_tasks: set,
    project_id: ProjectID,
    current_wallet_transaction: CreditTransactionCreateBody,
    new_wallet_transaction: CreditTransactionCreateBody,
):
    # NOTE: `current_wallet_transaction` is the Wallet in DEBT

    total_project_debt_amount = await service_runs_db.sum_project_wallet_total_credits(
        db_engine,
        product_name=current_wallet_transaction.product_name,
        wallet_id=current_wallet_transaction.wallet_id,
        project_id=project_id,
        transaction_status=CreditTransactionStatus.IN_DEBT,
    )

    if (
        total_project_debt_amount.available_osparc_credits
        != new_wallet_transaction.osparc_credits
    ):
        msg = f"Project DEBT of {total_project_debt_amount.available_osparc_credits} does not equal to payment: new_wallet {new_wallet_transaction.wallet_id} credits {new_wallet_transaction.osparc_credits}, current wallet {current_wallet_transaction.wallet_id} credits {current_wallet_transaction.osparc_credits}"
        raise WalletTransactionError(msg=msg)
    if (
        -total_project_debt_amount.available_osparc_credits
        != current_wallet_transaction.osparc_credits
    ):
        msg = f"Project DEBT of {total_project_debt_amount.available_osparc_credits} does not equal to payment: new_wallet {new_wallet_transaction.wallet_id} credits {new_wallet_transaction.osparc_credits}, current wallet {current_wallet_transaction.wallet_id} credits {current_wallet_transaction.osparc_credits}"
        raise WalletTransactionError(msg=msg)
    if current_wallet_transaction.product_name != new_wallet_transaction.product_name:
        msg = f"Currently we do not support credit exchange between different products. New wallet {new_wallet_transaction.wallet_id}, current wallet {current_wallet_transaction.wallet_id}"
        raise WalletTransactionError(msg=msg)

    # Does the new wallet has enough credits to pay the debt?
    new_wallet_total_credit_amount = await credit_transactions_db.sum_wallet_credits(
        db_engine,
        product_name=new_wallet_transaction.product_name,
        wallet_id=new_wallet_transaction.wallet_id,
    )
    if (
        new_wallet_total_credit_amount.available_osparc_credits
        + total_project_debt_amount.available_osparc_credits
        < 0
    ):
        msg = f"New wallet {new_wallet_transaction.wallet_id} doesn't have enough credits {new_wallet_total_credit_amount.available_osparc_credits} to pay the debt {total_project_debt_amount.available_osparc_credits} of current wallet {current_wallet_transaction.wallet_id}"
        raise WalletTransactionError(msg=msg)

    new_wallet_transaction_create = CreditTransactionCreate(
        product_name=new_wallet_transaction.product_name,
        wallet_id=new_wallet_transaction.wallet_id,
        wallet_name=new_wallet_transaction.wallet_name,
        pricing_plan_id=None,
        pricing_unit_id=None,
        pricing_unit_cost_id=None,
        user_id=new_wallet_transaction.user_id,
        user_email=new_wallet_transaction.user_email,
        osparc_credits=new_wallet_transaction.osparc_credits,
        transaction_status=CreditTransactionStatus.BILLED,
        transaction_classification=CreditClassification.DEDUCT_WALLET_EXCHANGE,
        service_run_id=None,
        payment_transaction_id=new_wallet_transaction.payment_transaction_id,
        licensed_item_purchase_id=None,
        created_at=new_wallet_transaction.created_at,
        last_heartbeat_at=new_wallet_transaction.created_at,
    )

    current_wallet_transaction_create = CreditTransactionCreate(
        product_name=current_wallet_transaction.product_name,
        wallet_id=current_wallet_transaction.wallet_id,
        wallet_name=current_wallet_transaction.wallet_name,
        pricing_plan_id=None,
        pricing_unit_id=None,
        pricing_unit_cost_id=None,
        user_id=current_wallet_transaction.user_id,
        user_email=current_wallet_transaction.user_email,
        osparc_credits=current_wallet_transaction.osparc_credits,
        transaction_status=CreditTransactionStatus.BILLED,
        transaction_classification=CreditClassification.ADD_WALLET_EXCHANGE,
        service_run_id=None,
        payment_transaction_id=current_wallet_transaction.payment_transaction_id,
        licensed_item_purchase_id=None,
        created_at=current_wallet_transaction.created_at,
        last_heartbeat_at=current_wallet_transaction.created_at,
    )

    async with transaction_context(db_engine) as conn:
        await credit_transactions_db.create_credit_transaction(
            db_engine, connection=conn, data=new_wallet_transaction_create
        )
        await credit_transactions_db.create_credit_transaction(
            db_engine, connection=conn, data=current_wallet_transaction_create
        )
        # Change status from `IN_DEBT` to `BILLED`
        await credit_transactions_db.batch_update_credit_transaction_status_for_in_debt_transactions(
            db_engine,
            connection=conn,
            project_id=project_id,
            wallet_id=current_wallet_transaction_create.wallet_id,
            transaction_status=CreditTransactionStatus.BILLED,
        )

    fire_and_forget_task(
        sum_credit_transactions_and_publish_to_rabbitmq(
            db_engine,
            rabbitmq_client=rabbitmq_client,
            product_name=new_wallet_transaction_create.product_name,
            wallet_id=new_wallet_transaction_create.wallet_id,  # <-- New wallet
        ),
        task_suffix_name=f"sum_and_publish_credits_wallet_id{new_wallet_transaction_create.wallet_id}",
        fire_and_forget_tasks_collection=rut_fire_and_forget_tasks,
    )
    fire_and_forget_task(
        sum_credit_transactions_and_publish_to_rabbitmq(
            db_engine,
            rabbitmq_client=rabbitmq_client,
            product_name=current_wallet_transaction_create.product_name,
            wallet_id=current_wallet_transaction_create.wallet_id,  # <-- Current wallet
        ),
        task_suffix_name=f"sum_and_publish_credits_wallet_id{current_wallet_transaction_create.wallet_id}",
        fire_and_forget_tasks_collection=rut_fire_and_forget_tasks,
    )
