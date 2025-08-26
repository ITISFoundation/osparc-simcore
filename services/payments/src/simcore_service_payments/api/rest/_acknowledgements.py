import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from models_library.api_schemas_payments.errors import (
    PaymentMethodNotFoundError,
    PaymentNotFoundError,
)
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.logging_utils import log_context

from ..._constants import ACKED, PGDB
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
from ...services.notifier import NotifierService
from ...services.resource_usage_tracker import ResourceUsageTrackerApi
from ._dependencies import (
    create_repository,
    get_current_session,
    get_from_app_state,
    get_rut_api,
)

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/payments/{payment_id}:ack")
async def acknowledge_payment(
    payment_id: PaymentID,
    ack: AckPayment,
    _session: Annotated[SessionData, Depends(get_current_session)],
    repo_pay: Annotated[
        PaymentsTransactionsRepo, Depends(create_repository(PaymentsTransactionsRepo))
    ],
    repo_methods: Annotated[
        PaymentsMethodsRepo, Depends(create_repository(PaymentsMethodsRepo))
    ],
    rut_api: Annotated[ResourceUsageTrackerApi, Depends(get_rut_api)],
    notifier: Annotated[NotifierService, Depends(get_from_app_state(NotifierService))],
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
            transaction = await payments.acknowledge_one_time_payment(
                repo_pay, payment_id=payment_id, ack=ack
            )
        except PaymentNotFoundError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
            ) from err

    assert f"{payment_id}" == f"{transaction.payment_id}"  # nosec
    background_tasks.add_task(
        payments.on_payment_completed,
        transaction,
        rut_api,
        notifier=notifier,
    )

    if ack.saved:
        if ack.saved.payment_method_id is None or not ack.saved.success:
            _logger.error(
                **create_troubleshootting_log_kwargs(
                    f"Got ack that {payment_id=} was completed but failed to save the payment-method used for the payment as requested.",
                    error=RuntimeError("Failed to save payment-method after payment"),
                    error_context={
                        "ack": ack,
                        "user_id": transaction.user_id,
                        "payment_id": payment_id,
                        "transaction": transaction,
                    },
                    tip="This issue is not critical. Since the payment-method could not be saved, "
                    "the user cannot use it in following payments and will have to re-introduce it manually"
                    "SEE https://github.com/ITISFoundation/osparc-simcore/issues/6902",
                )
            )
        else:
            inserted = await payments_methods.insert_payment_method(
                repo=repo_methods,
                payment_method_id=ack.saved.payment_method_id,
                user_id=transaction.user_id,
                wallet_id=transaction.wallet_id,
                ack=ack.saved,
            )

            background_tasks.add_task(
                payments_methods.on_payment_method_completed,
                payment_method=inserted,
                notifier=notifier,
            )


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknowledge_payment_method(
    payment_method_id: PaymentMethodID,
    ack: AckPaymentMethod,
    _session: Annotated[SessionData, Depends(get_current_session)],
    repo: Annotated[
        PaymentsMethodsRepo, Depends(create_repository(PaymentsMethodsRepo))
    ],
    notifier: Annotated[NotifierService, Depends(get_from_app_state(NotifierService))],
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

        assert f"{payment_method_id}" == f"{acked.payment_method_id}"  # nosec
        background_tasks.add_task(
            payments_methods.on_payment_method_completed,
            payment_method=acked,
            notifier=notifier,
        )
