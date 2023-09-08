import logging
from typing import Annotated

from fastapi import APIRouter
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
    ack: AckPaymentMethod,
    session: Annotated[SessionData, get_current_session],
):
    """completes (ie. ack) request initated by `/init`"""
    raise NotImplementedError


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknoledge_payment_method(
    payment_method_id: PaymentMethodID,
    ack: AckPayment,
    session: Annotated[SessionData, get_current_session],
):
    """completes (ie. ack) request initated by `/payments-methods:init`"""
    raise NotImplementedError
