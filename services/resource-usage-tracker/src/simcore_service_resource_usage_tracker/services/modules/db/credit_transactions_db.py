import logging
from decimal import Decimal
from typing import cast

import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import CreditTransactionId, CreditTransactionStatus
from models_library.services_types import ServiceRunID
from models_library.wallets import WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CreditTransactionNotFoundError,
)
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ....exceptions.errors import CreditTransactionNotCreatedDBError
from ....models.credit_transactions import (
    CreditTransactionCreate,
    CreditTransactionCreditsAndStatusUpdate,
    CreditTransactionCreditsUpdate,
)

_logger = logging.getLogger(__name__)


async def create_credit_transaction(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: CreditTransactionCreate,
) -> CreditTransactionId:
    async with transaction_context(engine, connection) as conn:
        insert_stmt = (
            resource_tracker_credit_transactions.insert()
            .values(
                product_name=data.product_name,
                wallet_id=data.wallet_id,
                wallet_name=data.wallet_name,
                pricing_plan_id=data.pricing_plan_id,
                pricing_unit_id=data.pricing_unit_id,
                pricing_unit_cost_id=data.pricing_unit_cost_id,
                user_id=data.user_id,
                user_email=data.user_email,
                osparc_credits=data.osparc_credits,
                transaction_status=data.transaction_status,
                transaction_classification=data.transaction_classification,
                service_run_id=data.service_run_id,
                payment_transaction_id=data.payment_transaction_id,
                licensed_item_purchase_id=data.licensed_item_purchase_id,
                created=data.created_at,
                last_heartbeat_at=data.last_heartbeat_at,
                modified=sa.func.now(),
            )
            .returning(resource_tracker_credit_transactions.c.transaction_id)
        )
        result = await conn.execute(insert_stmt)
    row = result.first()
    if row is None:
        raise CreditTransactionNotCreatedDBError(data=data)
    return cast(CreditTransactionId, row[0])


async def update_credit_transaction_credits(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: CreditTransactionCreditsUpdate,
) -> CreditTransactionId | None:
    async with transaction_context(engine, connection) as conn:
        update_stmt = (
            resource_tracker_credit_transactions.update()
            .values(
                modified=sa.func.now(),
                osparc_credits=data.osparc_credits,
                last_heartbeat_at=data.last_heartbeat_at,
            )
            .where(
                (
                    resource_tracker_credit_transactions.c.service_run_id
                    == data.service_run_id
                )
                & (
                    resource_tracker_credit_transactions.c.transaction_status
                    == CreditTransactionStatus.PENDING
                )
                & (
                    resource_tracker_credit_transactions.c.last_heartbeat_at
                    <= data.last_heartbeat_at
                )
            )
            .returning(resource_tracker_credit_transactions.c.service_run_id)
        )
        result = await conn.execute(update_stmt)
    row = result.first()
    if row is None:
        return None
    return cast(CreditTransactionId | None, row[0])


async def update_credit_transaction_credits_and_status(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: CreditTransactionCreditsAndStatusUpdate,
) -> CreditTransactionId | None:
    async with transaction_context(engine, connection) as conn:
        update_stmt = (
            resource_tracker_credit_transactions.update()
            .values(
                modified=sa.func.now(),
                osparc_credits=data.osparc_credits,
                transaction_status=data.transaction_status,
            )
            .where(
                (
                    resource_tracker_credit_transactions.c.service_run_id
                    == data.service_run_id
                )
                & (
                    resource_tracker_credit_transactions.c.transaction_status
                    == CreditTransactionStatus.PENDING
                )
            )
            .returning(resource_tracker_credit_transactions.c.service_run_id)
        )
        result = await conn.execute(update_stmt)
    row = result.first()
    if row is None:
        return None
    return cast(CreditTransactionId | None, row[0])


async def batch_update_credit_transaction_status_for_in_debt_transactions(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID | None = None,
    wallet_id: WalletID,
    transaction_status: CreditTransactionStatus,
) -> None:
    update_stmt = (
        resource_tracker_credit_transactions.update()
        .values(
            modified=sa.func.now(),
            transaction_status=transaction_status,
        )
        .where(
            (resource_tracker_credit_transactions.c.wallet_id == wallet_id)
            & (
                resource_tracker_credit_transactions.c.transaction_status
                == CreditTransactionStatus.IN_DEBT
            )
        )
    )

    if project_id:
        update_stmt = update_stmt.where(
            resource_tracker_service_runs.c.project_id == f"{project_id}"
        )
    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(update_stmt)
        # NOTE: see https://docs.sqlalchemy.org/en/20/tutorial/data_update.html#getting-affected-row-count-from-update-delete
        assert isinstance(result, CursorResult)  # nosec
        if result.rowcount:
            _logger.info(
                "Wallet %s and project %s transactions in DEBT were changed to BILLED. Num. of transaction %s",
                wallet_id,
                project_id,
                result.rowcount,
            )


async def sum_wallet_credits(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
) -> WalletTotalCredits:
    async with transaction_context(engine, connection) as conn:
        sum_stmt = sa.select(
            sa.func.sum(resource_tracker_credit_transactions.c.osparc_credits)
        ).where(
            (resource_tracker_credit_transactions.c.product_name == product_name)
            & (resource_tracker_credit_transactions.c.wallet_id == wallet_id)
            & (
                resource_tracker_credit_transactions.c.transaction_status.in_(
                    [
                        CreditTransactionStatus.BILLED,
                        CreditTransactionStatus.PENDING,
                        CreditTransactionStatus.IN_DEBT,
                    ]
                )
            )
        )

        result = await conn.execute(sum_stmt)
    row = result.first()
    if row is None or row[0] is None:
        return WalletTotalCredits(
            wallet_id=wallet_id, available_osparc_credits=Decimal(0)
        )
    return WalletTotalCredits(wallet_id=wallet_id, available_osparc_credits=row[0])


async def get_transaction_current_credits_by_service_run_id(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    service_run_id: ServiceRunID,
) -> Decimal:
    async with transaction_context(engine, connection) as conn:
        select_stmt = sa.select(
            resource_tracker_credit_transactions.c.osparc_credits
        ).where(
            resource_tracker_credit_transactions.c.service_run_id == f"{service_run_id}"
        )
        result = await conn.execute(select_stmt)
    row = result.one_or_none()
    if row is None:
        raise CreditTransactionNotFoundError(service_run_id=service_run_id)
    return Decimal(row[0])
