import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ..models.auth import SessionData
from ..models.schemas.acknowledgements import (
    AckPayment,
    AckPaymentMethod,
    PaymentID,
    PaymentMethodID,
)
from ._dependencies import get_current_session

_logger = logging.getLogger(__name__)


router = APIRouter()


async def on_payment_completed(
    payment_id: PaymentID, ack: AckPayment, session: SessionData
):
    _logger.debug(
        "payment completed: %s",
        f"{payment_id=}, {ack.success=}, {ack.message=}, {session.username=}",
    )
    _logger.debug("Notify front-end -> sio ")
    _logger.debug("Authorize inc/dec credits -> RUT")
    _logger.debug("Annotate RUT response")


@router.post("/payments/{payment_id}:ack")
async def acknoledge_payment(
    payment_id: PaymentID,
    ack: AckPayment,
    session: Annotated[SessionData, Depends(get_current_session)],
    background_tasks: BackgroundTasks,
):
    """completes (ie. ack) request initated by `/init`"""
    _logger.debug(
        "User %s is acknoledging payment with %s as %s", session, f"{payment_id=}", ack
    )
    _logger.debug("Validate and complete transaction -> DB")
    _logger.debug(
        "When annotated in db, respond and start a background task with the rest"
    )
    background_tasks.add_task(on_payment_completed, payment_id, ack, session)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknoledge_payment_method(
    payment_method_id: PaymentMethodID,
    ack: AckPaymentMethod,
    session: Annotated[SessionData, Depends(get_current_session)],
):
    """completes (ie. ack) request initated by `/payments-methods:init`"""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
