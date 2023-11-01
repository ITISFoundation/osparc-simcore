import logging
from decimal import Decimal

import arrow
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
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.rabbitmq import RPCRouter
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState

from ..._constants import PAG, PGDB
from ...db.payments_methods_repo import PaymentsMethodsRepo
from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...models.payments_gateway import GetPaymentMethod, InitPayment, InitPaymentMethod
from ...models.utils import merge_models
from ...services import payments_methods
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
        gateway = PaymentsGatewayApi.get_from_app_state(app)

        init = await gateway.init_payment_method(
            InitPaymentMethod(
                user_name=user_name,
                user_email=user_email,
                wallet_name=wallet_name,
            )
        )

        form_link = gateway.get_form_payment_method_url(init.payment_method_id)

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

    return PaymentMethodInitiated(
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
    # Prevents card from being used
    repo = PaymentsMethodsRepo(db_engine=app.state.engine)

    await repo.update_ack_payment_method(
        payment_method_id,
        completion_state=InitPromptAckFlowState.CANCELED,
        state_message="User cancelled",
    )

    # gateway delete
    gateway = PaymentsGatewayApi.get_from_app_state(app)
    await gateway.delete_payment_method(payment_method_id)

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

    repo = PaymentsMethodsRepo(db_engine=app.state.engine)
    acked_many = await repo.list_user_payment_methods(
        user_id=user_id, wallet_id=wallet_id
    )
    assert not any(acked.completed_at is None for acked in acked_many)  # nosec

    gateway: PaymentsGatewayApi = PaymentsGatewayApi.get_from_app_state(app)
    got_many: list[GetPaymentMethod] = await gateway.get_many_payment_methods(
        [acked.payment_method_id for acked in acked_many]
    )

    return [
        merge_models(got, acked)
        for acked, got in zip(acked_many, got_many, strict=True)
    ]


@router.expose()
async def get_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> PaymentMethodGet:

    repo = PaymentsMethodsRepo(db_engine=app.state.engine)
    acked = await repo.get_payment_method(
        payment_method_id, user_id=user_id, wallet_id=wallet_id
    )
    assert acked.state == InitPromptAckFlowState.SUCCESS  # nosec

    gateway: PaymentsGatewayApi = PaymentsGatewayApi.get_from_app_state(app)
    got: GetPaymentMethod = await gateway.get_payment_method(acked.payment_method_id)

    return merge_models(got, acked)


@router.expose()
async def delete_payment_method(
    app: FastAPI,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
):
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

    initiated_at = arrow.utcnow().datetime

    # check acked payment_method_id
    repo = PaymentsMethodsRepo(db_engine=app.state.engine)
    acked = await repo.get_payment_method(
        payment_method_id, user_id=user_id, wallet_id=wallet_id
    )

    # init -> gateway
    gateway: PaymentsGatewayApi = PaymentsGatewayApi.get_from_app_state(app)
    payment_inited = await gateway.init_payment_with_payment_method(
        acked.payment_method_id,
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=target_credits,
            user_name=user_name,
            user_email=user_email,
            wallet_name=wallet_name,
        ),
    )

    payment_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)
    payment_id = await payment_repo.insert_init_payment_transaction(
        payment_id=payment_inited.payment_id,
        price_dollars=amount_dollars,
        osparc_credits=target_credits,
        product_name=product_name,
        user_id=user_id,
        user_email=user_email,
        wallet_id=wallet_id,
        comment=comment,
        initiated_at=initiated_at,
    )

    return WalletPaymentInitiated(
        payment_id=f"{payment_id}",
        payment_form_url=None,
    )
