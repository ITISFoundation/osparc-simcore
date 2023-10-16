import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, TypeAlias

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy

from . import errors
from .models.payments_transactions import PaymentTransactionState, payments_transactions

_logger = logging.getLogger(__name__)


PaymentID: TypeAlias = str
PaymentTransactionRow: TypeAlias = RowProxy


UNSET: Final[str] = "__UNSET__"


@dataclass
class PaymentFailure:
    payment_id: str

    def __bool__(self):
        return False


class PaymentAlreadyExists(PaymentFailure):
    ...


class PaymentNotFound(PaymentFailure):
    ...


class PaymentAlreadyAcked(PaymentFailure):
    ...


async def insert_init_payment_transaction(
    connection: SAConnection,
    *,
    payment_id: str,
    price_dollars: Decimal,
    osparc_credits: Decimal,
    product_name: str,
    user_id: int,
    user_email: str,
    wallet_id: int,
    comment: str | None,
    initiated_at: datetime.datetime,
) -> PaymentID | PaymentAlreadyExists:
    """Annotates 'init' transaction in the database"""
    try:
        await connection.execute(
            payments_transactions.insert().values(
                payment_id=payment_id,
                price_dollars=price_dollars,
                osparc_credits=osparc_credits,
                product_name=product_name,
                user_id=user_id,
                user_email=user_email,
                wallet_id=wallet_id,
                comment=comment,
                initiated_at=initiated_at,
            )
        )
    except errors.UniqueViolation:
        return PaymentAlreadyExists(payment_id)

    return payment_id


_UNSET: Final[str] = "__UNSET__"


async def update_payment_transaction_state(
    connection: SAConnection,
    *,
    payment_id: str,
    completion_state: PaymentTransactionState,
    state_message: str | None = None,
    invoice_url: str | None = UNSET,
) -> PaymentTransactionRow | PaymentNotFound | PaymentAlreadyAcked:
    """ACKs payment by updating state with SUCCESS, ..."""
    if completion_state == PaymentTransactionState.PENDING:
        msg = f"cannot update state with {completion_state=} since it is already initiated"
        raise ValueError(msg)

    optional = {}
    if state_message:
        optional["state_message"] = state_message

    if completion_state == PaymentTransactionState.SUCCESS and invoice_url is None:
        _logger.warning(
            "Payment %s completed as %s without invoice (%s)",
            payment_id,
            state_message,
            f"{invoice_url=}",
        )

    if invoice_url != UNSET:
        optional["invoice_url"] = invoice_url

    async with connection.begin():
        row = await (
            await connection.execute(
                sa.select(
                    payments_transactions.c.initiated_at,
                    payments_transactions.c.completed_at,
                )
                .where(payments_transactions.c.payment_id == payment_id)
                .with_for_update()
            )
        ).fetchone()

        if row is None:
            return PaymentNotFound(payment_id=payment_id)

        if row.completed_at is not None:
            assert row.initiated_at < row.completed_at  # nosec
            return PaymentAlreadyAcked(payment_id=payment_id)

        assert row.initiated_at  # nosec

        result = await connection.execute(
            payments_transactions.update()
            .values(completed_at=sa.func.now(), state=completion_state, **optional)
            .where(payments_transactions.c.payment_id == payment_id)
            .returning(sa.literal_column("*"))
        )
        row = await result.first()
        assert row, "execute above should have caught this"  # nosec

        return row


async def get_user_payments_transactions(
    connection: SAConnection,
    *,
    user_id: int,
    offset: int | None = None,
    limit: int | None = None,
) -> tuple[int, list[PaymentTransactionRow]]:
    total_number_of_items = await connection.scalar(
        sa.select(sa.func.count())
        .select_from(payments_transactions)
        .where(payments_transactions.c.user_id == user_id)
    )
    assert total_number_of_items is not None  # nosec

    # NOTE: what if between these two calls there are new rows? can we get this in an atomic call?å
    stmt = (
        payments_transactions.select()
        .where(payments_transactions.c.user_id == user_id)
        .order_by(payments_transactions.c.created.desc())
    )  # newest first

    if offset is not None:
        # psycopg2.errors.InvalidRowCountInResultOffsetClause: OFFSET must not be negative
        stmt = stmt.offset(offset)

    if limit is not None:
        # InvalidRowCountInLimitClause: LIMIT must not be negative
        stmt = stmt.limit(limit)

    result: ResultProxy = await connection.execute(stmt)
    rows = await result.fetchall() or []
    return total_number_of_items, rows
