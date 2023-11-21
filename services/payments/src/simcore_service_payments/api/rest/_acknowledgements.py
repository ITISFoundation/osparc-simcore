import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from servicelib.logging_utils import log_context
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from ..._constants import ACKED, PGDB
from ...core.errors import PaymentMethodNotFoundError, PaymentNotFoundError
from ...db.payments_methods_repo import PaymentsMethodsRepo
from ...db.payments_transactions_repo import PaymentsTransactionsRepo
from ...models.auth import SessionData
from ...models.schemas.acknowledgements import (
    AckPayment,
    AckPaymentMethod,
    PaymentID,
    PaymentMethodID,
)
from ...services import payments, payments_methods
from ...services.resource_usage_tracker import ResourceUsageTrackerApi
from ._dependencies import get_current_session, get_repository, get_rut_api

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/payments/{payment_id}:ack")
async def acknowledge_payment(
    payment_id: PaymentID,
    ack: AckPayment,
    _session: Annotated[SessionData, Depends(get_current_session)],
    repo_pay: Annotated[
        PaymentsTransactionsRepo, Depends(get_repository(PaymentsTransactionsRepo))
    ],
    repo_methods: Annotated[
        PaymentsMethodsRepo, Depends(get_repository(PaymentsMethodsRepo))
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
            transaction = await repo_pay.update_ack_payment_transaction(
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

    if transaction.state == PaymentTransactionState.SUCCESS:
        assert f"{payment_id}" == f"{transaction.payment_id}"  # nosec
        background_tasks.add_task(payments.on_payment_completed, transaction, rut_api)

    if ack.saved:
        created = await payments_methods.create_payment_method(
            repo=repo_methods,
            payment_method_id=ack.saved.payment_method_id,
            user_id=transaction.user_id,
            wallet_id=transaction.wallet_id,
            ack=ack.saved,
        )
        background_tasks.add_task(payments_methods.on_payment_method_completed, created)


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknowledge_payment_method(
    payment_method_id: PaymentMethodID,
    ack: AckPaymentMethod,
    _session: Annotated[SessionData, Depends(get_current_session)],
    repo: Annotated[PaymentsMethodsRepo, Depends(get_repository(PaymentsMethodsRepo))],
    background_tasks: BackgroundTasks,
):
    """completes (ie. ack) request initated by `/payments-methods:init` on the payments-gateway API"""
    with log_context(
        _logger,
        logging.INFO,
        "%s: Update %s payment-method %s in db",
        PGDB,
        ACKED,
        f"{payment_method_id=}",
    ):
        try:

            acked = await payments_methods.acknowledge_creation_of_payment_method(
                repo=repo, payment_method_id=payment_method_id, ack=ack
            )
        except PaymentMethodNotFoundError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
            ) from err

    if acked.state == InitPromptAckFlowState.SUCCESS:
        assert f"{payment_method_id}" == f"{acked.payment_method_id}"  # nosec
        background_tasks.add_task(payments_methods.on_payment_method_completed, acked)
