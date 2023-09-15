from pydantic import BaseModel, Field

from ..payments_gateway import PaymentID, PaymentMethodID


class _BaseAck(BaseModel):
    success: bool
    message: str = Field(default=None)


class AckPaymentMethod(BaseModel):
    ...


class SavedPaymentMethod(AckPaymentMethod):
    payment_method_id: PaymentMethodID


class AckPayment(_BaseAck):
    saved: SavedPaymentMethod | None = Field(
        default=None,
        description="If not None, then the payment method used"
        "in this payment was alos saved, returning its payment_method_id and ack"
        "This happens when user marks 'save' during the payment prompt step.",
    )


assert PaymentID  # nosec
assert PaymentMethodID  # nosec


__all__: tuple[str, ...] = (
    "PaymentID",
    "PaymentMethodID",
)
