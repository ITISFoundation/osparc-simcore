import datetime
from decimal import Decimal

from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.users import UserID
from models_library.wallets import WalletID
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from ..models.db import PaymentsTransactionsDB


class PaymentsTransactionsRepo:
    #
    # Next PRs should move most of the implementations in
    # services/web/server/src/simcore_service_webserver/payments/_db.py
    # here.
    # The transition should put all the implementations in the simcore_postgres_database first
    # so it is usable temporarily in both the webserver and here
    #
    async def init_payment_transaction(
        self,
        payment_id: str,
        price_dollars: Decimal,
        osparc_credits: Decimal,
        product_name: str,
        user_id: UserID,
        user_email: str,
        wallet_id: WalletID,
        comment: str | None,
        initiated_at: datetime.datetime,
    ):
        raise NotImplementedError

    async def ack_payment_transaction(
        self,
        payment_id: PaymentID,
        completion_state: PaymentTransactionState,
        state_message: str | None,
    ) -> PaymentsTransactionsDB:
        raise NotImplementedError
