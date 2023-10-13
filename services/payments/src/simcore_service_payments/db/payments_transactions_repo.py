import datetime
from dataclasses import dataclass
from decimal import Decimal

from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl, PositiveInt
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
    payments_transactions,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..models.db import PaymentsTransactionsDB
from ..models.payments_gateway import PaymentID


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: AsyncEngine


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
        async with self.db_engine.connect() as conn:
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

    async def ack_payment_transaction(
        self,
        payment_id: PaymentID,
        completion_state: PaymentTransactionState,
        state_message: str | None,
        invoice_url: HttpUrl,
    ) -> PaymentsTransactionsDB:
        raise NotImplementedError

    async def list_user_payment_transactions(
        self,
        user_id: UserID,
        *,
        offset: PositiveInt,
        limit: PositiveInt,
    ) -> tuple[int, list[PaymentsTransactionsDB]]:
        """List payments done by a give user (any wallet)

        Sorted by newest-first
        """
        raise NotImplementedError
