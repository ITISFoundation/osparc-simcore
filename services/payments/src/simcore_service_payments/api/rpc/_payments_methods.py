import logging
from decimal import Decimal

import arrow
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentMethodID,
    PaymentMethodInit,
    WalletPaymentCreated,
)
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.rabbitmq import RPCRouter
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.models.payments_gateway import InitPaymentMethod

from ..._constants import PAG, PGDB
from ...db.payments_transactions_repo import PaymentsTransactionsRepo
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
) -> PaymentMethodInit:
    initiated_at = arrow.utcnow().datetime

    # Payment-Gateway
    with log_context(
        _logger,
        logging.INFO,
        "%s: Init payment-method %s in payments-gateway",
        PAG,
        f"{wallet_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        payments_gateway_api = PaymentsGatewayApi.get_from_app_state(app)

        init = await payments_gateway_api.init_payment_method(
            InitPaymentMethod(
                user_name=user_name,
                user_email=user_email,
                wallet_name=wallet_name,
            )
        )

        form_link = payments_gateway_api.get_form_payment_method_url(
            init.payment_method_id
        )

    # Database
    with log_context(
        _logger,
        logging.INFO,
        "%s: Annotate INIT payment-method %s in db",
        PGDB,
        f"{init.payment_method_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        repo = PaymentsMethodsRepo(db_engine=app.state.engine)
        payment_method_id = await repo.insert_init_payment_method(
            init.payment_method_id,
            user_id=user_id,
            wallet_id=wallet_id,
            initiated_at=initiated_at,
        )
        assert payment_method_id == init.payment_method_id  # nosec

    return PaymentMethodInit(
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
        payment_method_form_url=f"{form_link}",
    )


@router.expose()
async def cancel_creation_of_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    # TODO: with db transaction

    # Prevents card from being used
    repo = PaymentsMethodsRepo(db_engine=app.state.engine)

    await repo.update_ack_payment_method(
        payment_method_id,
        completion_state=InitPromptAckFlowState.CANCELED,
        state_message="User cancelled",
    )
    # TODO: Notify?

    # gateway delete
    payments_gateway_api = PaymentsGatewayApi.get_from_app_state(app)
    await payments_gateway_api.delete_payment_method(payment_method_id)

    # delete payment-method in db
    await repo.delete_payment_method(
        payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


@router.expose()
async def list_payment_methods(
    app: FastAPI,
    *,
    user_id: UserID,
    wallet_id: WalletID,
):
    raise NotImplementedError


@router.expose()
async def get_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
):
    raise NotImplementedError


@router.expose()
async def delete_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
):
    raise NotImplementedError


@router.expose()
async def init_payment_with_payment_method(
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
) -> WalletPaymentCreated:

    payment_id: PaymentID = "123"

    payments_gateway_api = PaymentsGatewayApi.get_from_app_state(app)

    repo = PaymentsTransactionsRepo(db_engine=app.state.engine)

    raise NotImplementedError
