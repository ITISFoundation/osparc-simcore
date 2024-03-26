import logging
from decimal import Decimal

from fastapi import FastAPI
from models_library.api_schemas_payments.errors import (
    PaymentsError,
    PaymentServiceUnavailableError,
)
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentTransaction,
    WalletPaymentInitiated,
)
from models_library.payments import UserInvoiceAddress
from models_library.products import ProductName, StripePriceID, StripeTaxRateID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, HttpUrl
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.rabbitmq import RPCRouter

from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...services import payments
from ...services.payments_gateway import PaymentsGatewayApi
from ...services.stripe import StripeApi

_logger = logging.getLogger(__name__)


router = RPCRouter()


@router.expose(reraise_if_error_type=(PaymentsError, PaymentServiceUnavailableError))
async def init_payment(  # pylint: disable=too-many-arguments
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
    user_address: UserInvoiceAddress,
    stripe_price_id: StripePriceID,
    stripe_tax_rate_id: StripeTaxRateID,
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
            user_address=user_address,
            stripe_price_id=stripe_price_id,
            stripe_tax_rate_id=stripe_tax_rate_id,
            comment=comment,
        )


@router.expose(reraise_if_error_type=(PaymentsError, PaymentServiceUnavailableError))
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


@router.expose(reraise_if_error_type=(PaymentsError, PaymentServiceUnavailableError))
async def get_payments_page(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[int, list[PaymentTransaction]]:
    return await payments.get_payments_page(
        repo=PaymentsTransactionsRepo(db_engine=app.state.engine),
        user_id=user_id,
        product_name=product_name,
        limit=limit,
        offset=offset,
    )


@router.expose(reraise_if_error_type=(PaymentsError, PaymentServiceUnavailableError))
async def get_payment_invoice_url(
    app: FastAPI,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_id: PaymentID,
) -> HttpUrl:
    return await payments.get_payment_invoice_url(
        repo=PaymentsTransactionsRepo(db_engine=app.state.engine),
        stripe_api=StripeApi.get_from_app_state(app),
        user_id=user_id,
        wallet_id=wallet_id,
        payment_id=payment_id,
    )
