import logging
from decimal import Decimal

import arrow
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.rabbitmq import RPCRouter

from ..._constants import PAG, PGDB
from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...models.payments_gateway import InitPayment
from ...services.payments_gateway import PaymentsGatewayApi

_logger = logging.getLogger(__name__)


router = RPCRouter()


@router.expose()
async def init_payment(
    app: FastAPI,
    *,
    amount_dollars: Decimal,
    target_credits: Decimal,
    product_name: str,
    wallet_id: WalletID,
    wallet_name: str,
    user_id: UserID,
    user_name: str,
    user_email: str,
    comment: str | None = None,
) -> WalletPaymentCreated:
    initiated_at = arrow.utcnow().datetime

    # Payment-Gateway
    with log_context(
        _logger,
        logging.INFO,
        "%s: Init payment %s in payments-gateway",
        PAG,
        f"{wallet_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        payments_gateway_api = PaymentsGatewayApi.get_from_app_state(app)

        init = await payments_gateway_api.init_payment(
            payment=InitPayment(
                amount_dollars=amount_dollars,
                credits_=target_credits,
                user_name=user_name,
                user_email=user_email,  # type: ignore
                wallet_name=wallet_name,
            )
        )

        submission_link = payments_gateway_api.get_form_payment_url(init.payment_id)

    # Database
    with log_context(
        _logger,
        logging.INFO,
        "%s: Annotate INIT transaction %s in db",
        PGDB,
        f"{init.payment_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        repo = PaymentsTransactionsRepo(db_engine=app.state.engine)
        payment_id = await repo.insert_init_payment_transaction(
            payment_id=init.payment_id,
            price_dollars=amount_dollars,
            osparc_credits=target_credits,
            product_name=product_name,
            user_id=user_id,
            user_email=user_email,
            wallet_id=wallet_id,
            comment=comment,
            initiated_at=initiated_at,
        )
        assert payment_id == init.payment_id  # nosec

    return WalletPaymentCreated(
        payment_id=f"{payment_id}",
        payment_form_url=f"{submission_link}",
    )
