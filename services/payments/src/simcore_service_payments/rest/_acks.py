import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from simcore_service_payments.services.auth import SessionData

from ..models.schemas.acks import (
    AckPayment,
    AckPaymentMethod,
    PaymentID,
    PaymentMethodID,
)
from ._dependencies import get_current_session

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/payments/{payment_id}:ack")
async def acknoledge_payment(
    payment_id: PaymentID,
    ack: AckPayment,
    session: Annotated[SessionData, Depends(get_current_session)],
):
    """completes (ie. ack) request initated by `/init`"""
    _logger.debug(
        "Validate and complete transaction %s %s -> DB", f"{payment_id=}", f"{ack=}"
    )
    _logger.debug("When annotated in db, respond. Now we start a background task")
    _logger.debug("Notify front-end -> sio")
    _logger.debug("Authorize inc/dec credits -> RUT")
    _logger.debug("Annotate response")
    raise NotImplementedError


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknoledge_payment_method(
    payment_method_id: PaymentMethodID,
    ack: AckPaymentMethod,
    session: Annotated[SessionData, Depends(get_current_session)],
):
    """completes (ie. ack) request initated by `/payments-methods:init`"""
    raise NotImplementedError
