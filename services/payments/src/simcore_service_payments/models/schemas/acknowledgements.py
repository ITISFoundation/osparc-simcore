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
        description="If the user decided to save the payment method"
        "after payment it returns the payment-method acknoledgement response."
        "Otherwise it defaults to None.",
    )


assert PaymentID  # nosec
assert PaymentMethodID  # nosec


__all__: tuple[str, ...] = (
    "PaymentID",
    "PaymentMethodID",
)
