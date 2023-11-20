""" Functions here support two types of payments worklows:
- One-time payment
- Payment w/ payment-method

"""
# pylint: disable=too-many-arguments

import logging
import uuid
from decimal import Decimal

import arrow
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentMethodID,
    PaymentTransaction,
    WalletPaymentInitiated,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, PositiveInt
from servicelib.logging_utils import log_context
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt

from .._constants import RUT
from ..core.errors import (
    PaymentAlreadyAckedError,
    PaymentAlreadyExistsError,
    PaymentNotFoundError,
)
from ..db.payments_transactions_repo import PaymentsTransactionsRepo
from ..models.db import PaymentsTransactionsDB
from ..models.payments_gateway import InitPayment, PaymentInitiated
from ..models.schemas.acknowledgements import AckPayment, AckPaymentWithPaymentMethod
from ..services.resource_usage_tracker import ResourceUsageTrackerApi
from .payments_gateway import PaymentsGatewayApi

_logger = logging.getLogger()


async def init_one_time_payment(
    gateway: PaymentsGatewayApi,
    repo: PaymentsTransactionsRepo,
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
    initiated_at = arrow.utcnow().datetime

    init = await gateway.init_payment(
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=target_credits,
            user_name=user_name,
            user_email=user_email,
            wallet_name=wallet_name,
        )
    )

    submission_link = gateway.get_form_payment_url(init.payment_id)

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

    return WalletPaymentInitiated(
        payment_id=f"{payment_id}",
        payment_form_url=f"{submission_link}",
    )


async def cancel_one_time_payment(
    gateway: PaymentsGatewayApi,
    repo: PaymentsTransactionsRepo,
    *,
    payment_id: PaymentID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    payment = await repo.get_payment_transaction(
        payment_id=payment_id, user_id=user_id, wallet_id=wallet_id
    )

    if payment is None:
        raise PaymentNotFoundError(payment_id=payment_id)

    if payment.state.is_completed():
        if payment.state == PaymentTransactionState.CANCELED:
            # Avoids error if multiple cancel calls
            return
        raise PaymentAlreadyAckedError(payment_id=payment_id)

    payment_cancelled = await gateway.cancel_payment(
        PaymentInitiated(payment_id=payment_id)
    )

    await repo.update_ack_payment_transaction(
        payment_id=payment_id,
        completion_state=PaymentTransactionState.CANCELED,
        state_message=payment_cancelled.message,
        invoice_url=None,
    )


async def acknowledge_one_time_payment(
    repo_transactions: PaymentsTransactionsRepo,
    *,
    payment_id: PaymentID,
    ack: AckPayment,
) -> PaymentsTransactionsDB:
    return await repo_transactions.update_ack_payment_transaction(
        payment_id=payment_id,
        completion_state=(
            PaymentTransactionState.SUCCESS
            if ack.success
            else PaymentTransactionState.FAILED
        ),
        state_message=ack.message,
        invoice_url=ack.invoice_url,
    )


async def on_payment_completed(
    transaction: PaymentsTransactionsDB, rut_api: ResourceUsageTrackerApi
):
    assert transaction.completed_at is not None  # nosec
    assert transaction.initiated_at < transaction.completed_at  # nosec

    _logger.debug(
        "Notify front-end of payment -> sio SOCKET_IO_PAYMENT_COMPLETED_EVENT "
    )

    with log_context(
        _logger,
        logging.INFO,
        "%s: Top-up %s credits for %s",
        RUT,
        f"{transaction.osparc_credits}",
        f"{transaction.payment_id=}",
    ):
        credit_transaction_id = await rut_api.create_credit_transaction(
            product_name=transaction.product_name,
            wallet_id=transaction.wallet_id,
            wallet_name=f"id={transaction.wallet_id}",
            user_id=transaction.user_id,
            user_email=transaction.user_email,
            osparc_credits=transaction.osparc_credits,
            payment_transaction_id=transaction.payment_id,
            created_at=transaction.completed_at,
        )

    _logger.debug(
        "%s: Response to %s was %s",
        RUT,
        f"{transaction.payment_id=}",
        f"{credit_transaction_id=}",
    )


async def pay_with_payment_method(  # noqa: PLR0913
    gateway: PaymentsGatewayApi,
    rut: ResourceUsageTrackerApi,
    repo_transactions: PaymentsTransactionsRepo,
    repo_methods: PaymentsMethodsRepo,
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
) -> PaymentTransaction:
    initiated_at = arrow.utcnow().datetime

    acked = await repo_methods.get_payment_method(
        payment_method_id, user_id=user_id, wallet_id=wallet_id
    )

    ack: AckPaymentWithPaymentMethod = await gateway.pay_with_payment_method(
        acked.payment_method_id,
        payment=InitPayment(
            amount_dollars=amount_dollars,
            credits=target_credits,
            user_name=user_name,
            user_email=user_email,
            wallet_name=wallet_name,
        ),
    )

    payment_id = ack.payment_id

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(PaymentAlreadyExistsError),
        reraise=True,
    ):
        with attempt:
            payment_id = await repo_transactions.insert_init_payment_transaction(
                ack.payment_id or f"{uuid.uuid4()}",
                price_dollars=amount_dollars,
                osparc_credits=target_credits,
                product_name=product_name,
                user_id=user_id,
                user_email=user_email,
                wallet_id=wallet_id,
                comment=comment,
                initiated_at=initiated_at,
            )

    assert payment_id is not None  # nosec

    transaction = await repo_transactions.update_ack_payment_transaction(
        payment_id=payment_id,
        completion_state=(
            PaymentTransactionState.SUCCESS
            if ack.success
            else PaymentTransactionState.FAILED
        ),
        state_message=ack.message,
        invoice_url=ack.invoice_url,
    )

    await on_payment_completed(transaction, rut)

    return transaction.to_api_model()


async def get_payments_page(
    repo: PaymentsTransactionsRepo,
    *,
    user_id: UserID,
    limit: PositiveInt | None = None,
    offset: PositiveInt | None = None,
) -> tuple[int, list[PaymentTransaction]]:
    """All payments associated to a user (i.e. including all the owned wallets)"""

    total_number_of_items, page = await repo.list_user_payment_transactions(
        user_id=user_id, offset=offset, limit=limit
    )

    return total_number_of_items, [t.to_api_model() for t in page]
