""" This service just keeps a reference of the payment method `payment_method_id`
and all the details are stored externaly.

The creation of this resource can use any of these two workflows:
1. init-prompt-ack workflow
    - init_creation_of_payment_method
    - cancel_creation_of_payment_method (optional)
    - acknowledge_creation_of_payment_method
2. direct creation
    - create_payment_method

This resource can also be read or deleted using
- list_payments_methods
- get_payment_method
- delete_payment_method

"""
import logging

import arrow
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInitiated,
)
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState

from ..db.payments_methods_repo import PaymentsMethodsRepo
from ..models.db import PaymentsMethodsDB
from ..models.payments_gateway import GetPaymentMethod, InitPaymentMethod
from ..models.schemas.acknowledgements import AckPaymentMethod
from ..models.utils import merge_models
from .payments_gateway import PaymentsGatewayApi

_logger = logging.getLogger(__name__)


async def init_creation_of_payment_method(
    gateway: PaymentsGatewayApi,
    repo: PaymentsMethodsRepo,
    *,
    wallet_id: WalletID,
    wallet_name: IDStr,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
) -> PaymentMethodInitiated:
    initiated_at = arrow.utcnow().datetime

    init = await gateway.init_payment_method(
        InitPaymentMethod(
            user_name=user_name,
            user_email=user_email,
            wallet_name=wallet_name,
        )
    )
    form_link = gateway.get_form_payment_method_url(init.payment_method_id)

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


async def cancel_creation_of_payment_method(
    gateway: PaymentsGatewayApi,
    repo: PaymentsMethodsRepo,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
):
    # Prevents card from being used
    await repo.update_ack_payment_method(
        payment_method_id,
        completion_state=InitPromptAckFlowState.CANCELED,
        state_message="User cancelled",
    )

    # gateway delete
    await gateway.delete_payment_method(payment_method_id)

    # delete payment-method in db
    await repo.delete_payment_method(
        payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


async def acknowledge_creation_of_payment_method(
    repo: PaymentsMethodsRepo,
    *,
    payment_method_id: PaymentMethodID,
    ack: AckPaymentMethod,
) -> PaymentsMethodsDB:
    return await repo.update_ack_payment_method(
        payment_method_id=payment_method_id,
        completion_state=(
            InitPromptAckFlowState.SUCCESS
            if ack.success
            else InitPromptAckFlowState.FAILED
        ),
        state_message=ack.message,
    )


async def on_payment_method_completed(payment_method: PaymentsMethodsDB):
    assert payment_method.state == InitPromptAckFlowState.SUCCESS  # nosec
    assert payment_method.completed_at is not None  # nosec
    assert payment_method.initiated_at < payment_method.completed_at  # nosec

    _logger.debug(
        "Notify front-end of payment -> sio (SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT) "
    )


async def create_payment_method(
    repo: PaymentsMethodsRepo,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
    ack: AckPaymentMethod,
) -> PaymentsMethodsDB:
    """Direct creation of payment-method"""
    return await repo.insert_payment_method(
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        completion_state=InitPromptAckFlowState.SUCCESS
        if ack.success
        else InitPromptAckFlowState.FAILED,
        state_message=ack.message,
    )


async def list_payment_methods(
    gateway: PaymentsGatewayApi,
    repo: PaymentsMethodsRepo,
    *,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[PaymentMethodGet]:
    acked_many = await repo.list_user_payment_methods(
        user_id=user_id, wallet_id=wallet_id
    )
    assert not any(acked.completed_at is None for acked in acked_many)  # nosec

    got_many: list[GetPaymentMethod] = await gateway.get_many_payment_methods(
        [acked.payment_method_id for acked in acked_many]
    )

    return [
        merge_models(got, acked)
        for acked, got in zip(acked_many, got_many, strict=True)
    ]


async def get_payment_method(
    gateway: PaymentsGatewayApi,
    repo: PaymentsMethodsRepo,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> PaymentMethodGet:
    acked = await repo.get_payment_method(
        payment_method_id, user_id=user_id, wallet_id=wallet_id
    )
    assert acked.state == InitPromptAckFlowState.SUCCESS  # nosec

    got: GetPaymentMethod = await gateway.get_payment_method(acked.payment_method_id)
    return merge_models(got, acked)


async def delete_payment_method(
    gateway: PaymentsGatewayApi,
    repo: PaymentsMethodsRepo,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
):
    acked = await repo.get_payment_method(
        payment_method_id, user_id=user_id, wallet_id=wallet_id
    )

    await gateway.delete_payment_method(acked.payment_method_id)

    await repo.delete_payment_method(
        acked.payment_method_id, user_id=acked.user_id, wallet_id=acked.wallet_id
    )
