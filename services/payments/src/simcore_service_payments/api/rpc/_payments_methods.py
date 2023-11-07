import logging
from decimal import Decimal

from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInitiated,
    WalletPaymentInitiated,
)
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr
from servicelib.rabbitmq import RPCRouter

from ...db.payments_methods_repo import PaymentsMethodsRepo
from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...services import payments, payments_methods
from ...services.payments_gateway import PaymentsGatewayApi

_logger = logging.getLogger(__name__)


router = RPCRouter()


@router.expose()
async def init_creation_of_payment_method(
    app: FastAPI,
    *,
    wallet_id: WalletID,
    wallet_name: IDStr,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
) -> PaymentMethodInitiated:
    return await payments_methods.init_creation_of_payment_method(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        repo=PaymentsMethodsRepo(db_engine=app.state.engine),
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
    )


@router.expose()
async def cancel_creation_of_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    await payments_methods.cancel_creation_of_payment_method(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        repo=PaymentsMethodsRepo(db_engine=app.state.engine),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


@router.expose()
async def list_payment_methods(
    app: FastAPI,
    *,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[PaymentMethodGet]:
    return await payments_methods.list_payments_methods(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        repo=PaymentsMethodsRepo(db_engine=app.state.engine),
        user_id=user_id,
        wallet_id=wallet_id,
    )


@router.expose()
async def get_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> PaymentMethodGet:
    return await payments_methods.get_payment_method(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        repo=PaymentsMethodsRepo(db_engine=app.state.engine),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


@router.expose()
async def delete_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    await payments_methods.delete_payment_method(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        repo=PaymentsMethodsRepo(db_engine=app.state.engine),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


@router.expose()
async def init_payment_with_payment_method(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
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
    return await payments.init_payment_with_payment_method(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        repo_transactions=PaymentsTransactionsRepo(db_engine=app.state.engine),
        repo_methods=PaymentsMethodsRepo(db_engine=app.state.engine),
        payment_method_id=payment_method_id,
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
