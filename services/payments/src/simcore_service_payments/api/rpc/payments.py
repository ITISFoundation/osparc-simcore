import logging
from decimal import Decimal

from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from models_library.users import UserID

from ..db.payments_transactions import PaymentsTransactionsRepo
from ..models.payments_gateway import InitPayment
from ..services.payments_gateway import PaymentGatewayApi

_logger = logging.getLogger(__name__)


async def create_payment(
    app: FastAPI,
    amount_dollars: Decimal,
    target_credits: Decimal,
    product_name: str,
    wallet_id: str,
    wallet_name: str,
    user_id: UserID,
    user_name: str,
    user_email: str,
) -> WalletPaymentCreated:
    # Payment-Gateway
    payments_gateway_api = PaymentGatewayApi.get_from_state(app)

    init = await payments_gateway_api.init_payment(
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=target_credits,
            user_name=user_name,
            user_email=user_email,
            wallet_name=wallet_name,
        )
    )

    submission_link = payments_gateway_api.get_form_payment_url(init.payment_id)

    # Database
    repo = PaymentsTransactionsRepo()
    _logger.debug("Annotate transaction %s", repo)

    return WalletPaymentCreated.construct(
        payment_id=init.payment_id,
        payment_form_url=f"{submission_link}",
    )
