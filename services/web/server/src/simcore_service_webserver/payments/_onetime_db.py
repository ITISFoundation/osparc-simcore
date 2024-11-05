import datetime
import logging
from decimal import Decimal

import sqlalchemy as sa
from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, HttpUrl, PositiveInt, TypeAdapter
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
    payments_transactions,
)
from simcore_postgres_database.utils_payments import (
    PaymentAlreadyAcked,
    PaymentNotFound,
    get_user_payments_transactions,
    update_payment_transaction_state,
)

from ..db.plugin import get_database_engine
from .errors import PaymentCompletedError, PaymentNotFoundError

_logger = logging.getLogger(__name__)


#
# NOTE: this will be moved to the payments service
# NOTE: with https://sqlmodel.tiangolo.com/ we would only define this once!
class PaymentsTransactionsDB(BaseModel):
    payment_id: PaymentID
    price_dollars: Decimal  # accepts negatives
    osparc_credits: Decimal  # accepts negatives
    product_name: ProductName
    user_id: UserID
    user_email: LowerCaseEmailStr
    wallet_id: WalletID
    comment: str | None
    invoice_url: HttpUrl | None
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    state: PaymentTransactionState
    state_message: str | None
    model_config = ConfigDict(from_attributes=True)


async def list_user_payment_transactions(
    app,
    *,
    user_id: UserID,
    offset: PositiveInt,
    limit: PositiveInt,
) -> tuple[int, list[PaymentsTransactionsDB]]:
    """List payments done by a give user (any wallet)

    Sorted by newest-first
    """
    async with get_database_engine(app).acquire() as conn:
        total_number_of_items, rows = await get_user_payments_transactions(
            conn, user_id=user_id, offset=offset, limit=limit
        )
        page = TypeAdapter(list[PaymentsTransactionsDB]).validate_python(rows)
        return total_number_of_items, page


async def get_pending_payment_transactions_ids(app: web.Application) -> list[PaymentID]:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            sa.select(payments_transactions.c.payment_id)
            .where(payments_transactions.c.completed_at == None)  # noqa: E711
            .order_by(payments_transactions.c.initiated_at.asc())  # oldest first
        )
        rows = await result.fetchall() or []
        return [TypeAdapter(PaymentID).validate_python(row.payment_id) for row in rows]


async def complete_payment_transaction(
    app: web.Application,
    *,
    payment_id: PaymentID,
    completion_state: PaymentTransactionState,
    state_message: str | None,
    invoice_url: HttpUrl | None = None,
) -> PaymentsTransactionsDB:
    """

    Raises:
        PaymentNotFoundError
        PaymentCompletedError
    """
    optional_kwargs = {}
    if invoice_url:
        optional_kwargs["invoice_url"] = invoice_url

    async with get_database_engine(app).acquire() as conn:
        row = await update_payment_transaction_state(
            conn,
            payment_id=payment_id,
            completion_state=completion_state,
            state_message=state_message,
            **optional_kwargs,  # type: ignore[arg-type]
        )

        if isinstance(row, PaymentNotFound):
            raise PaymentNotFoundError(payment_id=row.payment_id)

        if isinstance(row, PaymentAlreadyAcked):
            raise PaymentCompletedError(payment_id=row.payment_id)

        assert row  # nosec
        return PaymentsTransactionsDB.model_validate(row)
