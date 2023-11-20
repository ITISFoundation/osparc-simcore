import logging
from decimal import Decimal

from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentTransaction,
    WalletPaymentInitiated,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.rabbitmq import RPCRouter

from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...services import payments
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
    user_email: EmailStr,
    comment: str | None = None,
) -> WalletPaymentInitiated:

    with log_context(
        _logger,
        logging.INFO,
        "Init payment to %s",
        f"{wallet_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        return await payments.init_one_time_payment(
            gateway=PaymentsGatewayApi.get_from_app_state(app),
            repo=PaymentsTransactionsRepo(db_engine=app.state.engine),
            amount_dollars=amount_dollars,
            target_credits=target_credits,
            product_name=product_name,
            wallet_id=wallet_id,
            wallet_name=wallet_name,
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            comment=comment,
        )


@router.expose()
async def cancel_payment(
    app: FastAPI,
    *,
    payment_id: PaymentID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:

    with log_context(
        _logger,
        logging.INFO,
        "Cancel payment in %s",
        f"{wallet_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        await payments.cancel_one_time_payment(
            gateway=PaymentsGatewayApi.get_from_app_state(app),
            repo=PaymentsTransactionsRepo(db_engine=app.state.engine),
            payment_id=payment_id,
            user_id=user_id,
            wallet_id=wallet_id,
        )


@router.expose()
async def get_payments_page(
    app: FastAPI,
    *,
    user_id: UserID,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[int, list[PaymentTransaction]]:
    return await payments.get_payments_page(
        repo=PaymentsTransactionsRepo(db_engine=app.state.engine),
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
