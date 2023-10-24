import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from servicelib.logging_utils import log_context
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from ..._constants import ACKED, PGDB, RUT
from ...core.errors import PaymentNotFoundError
from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...models.auth import SessionData
from ...models.db import PaymentsTransactionsDB
from ...models.schemas.acknowledgements import (
    AckPayment,
    AckPaymentMethod,
    PaymentID,
    PaymentMethodID,
)
from ...services.resource_usage_tracker import ResourceUsageTrackerApi
from ._dependencies import get_current_session, get_repository, get_rut_api

_logger = logging.getLogger(__name__)


router = APIRouter()


async def on_payment_completed(
    transaction: PaymentsTransactionsDB, rut_api: ResourceUsageTrackerApi
):
    assert transaction.completed_at is not None  # nosec
    assert transaction.initiated_at < transaction.completed_at  # nosec

    _logger.debug("TODO next PR Notify front-end of payment -> sio ")

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
            wallet_name="id={transaction.wallet_id}",
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


@router.post("/payments/{payment_id}:ack")
async def acknowledge_payment(
    payment_id: PaymentID,
    ack: AckPayment,
    _session: Annotated[SessionData, Depends(get_current_session)],
    repo: Annotated[
        PaymentsTransactionsRepo, Depends(get_repository(PaymentsTransactionsRepo))
    ],
    rut_api: Annotated[ResourceUsageTrackerApi, Depends(get_rut_api)],
    background_tasks: BackgroundTasks,
):
    """completes (ie. ack) request initated by `/init` on the payments-gateway API"""

    with log_context(
        _logger,
        logging.INFO,
        "%s: Update %s transaction %s in db",
        PGDB,
        ACKED,
        f"{payment_id=}",
    ):
        try:
            transaction = await repo.update_ack_payment_transaction(
                payment_id=payment_id,
                completion_state=(
                    PaymentTransactionState.SUCCESS
                    if ack.success
                    else PaymentTransactionState.FAILED
                ),
                state_message=ack.message,
                invoice_url=ack.invoice_url,
            )
        except PaymentNotFoundError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
            ) from err

    if ack.saved:
        _logger.debug("%s: Creating payment method", PGDB)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )

    if transaction.state == PaymentTransactionState.SUCCESS:
        assert payment_id == transaction.payment_id  # nosec
        background_tasks.add_task(on_payment_completed, transaction, rut_api)


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknowledge_payment_method(
    payment_method_id: PaymentMethodID,
    ack: AckPaymentMethod,
    session: Annotated[SessionData, Depends(get_current_session)],
):
    """completes (ie. ack) request initated by `/payments-methods:init` on the payments-gateway API"""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
