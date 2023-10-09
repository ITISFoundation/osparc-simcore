import logging
from decimal import Decimal

from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...models.payments_gateway import InitPayment
from ...services.payments_gateway import PaymentsGatewayApi

_logger = logging.getLogger(__name__)


router = RPCRouter()


@router.expose()
async def create_payment(
    app: FastAPI,
    *,
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
    payments_gateway_api = PaymentsGatewayApi.get_from_app_state(app)

    init = await payments_gateway_api.init_payment(
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=target_credits,
            user_name=user_name,
            user_email=user_email,  # type: ignore
            wallet_name=wallet_name,
        )
    )

    submission_link = payments_gateway_api.get_form_payment_url(init.payment_id)

    # Database
    repo = PaymentsTransactionsRepo()
    _logger.debug(
        "Annotate transaction %s: %s",
        repo,
        {
            "amount_dollars": amount_dollars,
            "target_credits": target_credits,
            "product_name": product_name,
            "wallet_id": wallet_id,
            "wallet_name": wallet_name,
            "user_id": user_id,
            "user_name": user_name,
            "user_email": user_email,
        },
    )

    return WalletPaymentCreated(
        payment_id=f"{init.payment_id}",
        payment_form_url=f"{submission_link}",
    )
