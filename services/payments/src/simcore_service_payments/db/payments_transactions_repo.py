import datetime
from decimal import Decimal

import sqlalchemy as sa
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl, PositiveInt, parse_obj_as
from pydantic.errors import PydanticErrorMixin
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
    payments_transactions,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..models.db import PaymentsTransactionsDB
from ..models.payments_gateway import PaymentID

#
# Errors
#


class PaymentsValueError(PydanticErrorMixin, ValueError):
    ...


class PaymentAlreadyExistsError(PaymentsValueError):
    ...


class PaymentNotFoundError(PaymentsValueError):
    ...


class PaymentAlreadyAckedError(PaymentsValueError):
    ...


#
# base
#


class BaseRepository:
    """
    Repositories are pulled at every request
    """

    def __init__(self, db_engine: AsyncEngine):
        assert db_engine is not None  # nosec
        self.db_engine = db_engine


#
# repo
#


class PaymentsTransactionsRepo(BaseRepository):
    #
    # Next PRs should move most of the implementations in
    # services/web/server/src/simcore_service_webserver/payments/_db.py
    # here.
    # The transition should put all the implementations in the simcore_postgres_database first
    # so it is usable temporarily in both the webserver and here
    #
    async def insert_init_payment_transaction(
        self,
        payment_id: PaymentID,
        price_dollars: Decimal,
        osparc_credits: Decimal,
        product_name: str,
        user_id: UserID,
        user_email: str,
        wallet_id: WalletID,
        comment: str | None,
        initiated_at: datetime.datetime,
    ) -> PaymentID:
        """Annotates init-payment transaction"""
        async with self.db_engine.begin() as conn:
            await conn.execute(
                payments_transactions.insert().values(
                    payment_id=f"{payment_id}",
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
            return payment_id

    async def update_ack_payment_transaction(
        self,
        payment_id: PaymentID,
        completion_state: PaymentTransactionState,
        state_message: str | None,
        invoice_url: HttpUrl,
    ) -> PaymentsTransactionsDB:
        """

        - ACKs payment by updating state with SUCCESS, ...

        """
        if completion_state == PaymentTransactionState.PENDING:
            msg = f"cannot update state with {completion_state=} since it is already initiated"
            raise ValueError(msg)

        optional = {}
        if state_message:
            optional["state_message"] = state_message

        async with self.db_engine.begin() as connection:
            row = (
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
                raise PaymentNotFoundError(payment_id=payment_id)

            if row.completed_at is not None:
                assert row.initiated_at < row.completed_at  # nosec
                raise PaymentAlreadyAckedError(payment_id=payment_id)

            assert row.initiated_at  # nosec

            result = await connection.execute(
                payments_transactions.update()
                .values(
                    completed_at=sa.func.now(),
                    state=completion_state,
                    invoice_url=invoice_url,
                    **optional,
                )
                .where(payments_transactions.c.payment_id == payment_id)
                .returning(sa.literal_column("*"))
            )
            row = result.first()
            assert row, "execute above should have caught this"  # nosec

            return PaymentsTransactionsDB.from_orm(row)

    async def list_user_payment_transactions(
        self,
        user_id: UserID,
        *,
        offset: PositiveInt | None = None,
        limit: PositiveInt | None = None,
    ) -> tuple[int, list[PaymentsTransactionsDB]]:
        """List payments done by a give user (any wallet)

        Sorted by newest-first
        """
        async with self.db_engine.begin() as connection:
            result = await connection.execute(
                sa.select(sa.func.count())
                .select_from(payments_transactions)
                .where(payments_transactions.c.user_id == user_id)
            )
            total_number_of_items = result.scalar()
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

            result = await connection.execute(stmt)
            rows = result.fetchall()
            return total_number_of_items, parse_obj_as(
                list[PaymentsTransactionsDB], rows
            )
