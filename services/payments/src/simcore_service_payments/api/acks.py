import logging

from fastapi import APIRouter

from ..models.schemas.acks import (
    AckPayment,
    AckPaymentMethod,
    PaymentID,
    PaymentMethodID,
)

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/payments/{payment_id}:ack")
async def acknoledge_payment(payment_id: PaymentID, ack: AckPaymentMethod):
    """completes (ie. ack) request initated by `/init`"""
    raise NotImplementedError


@router.post("/payments-methods/{payment_method_id}:ack")
async def acknoledge_payment_method(
    payment_method_id: PaymentMethodID, ack: AckPayment
):
    """completes (ie. ack) request initated by `/payments-methods:init`"""
    raise NotImplementedError
