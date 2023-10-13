from pydantic import BaseModel, Field, HttpUrl

from ..payments_gateway import PaymentID, PaymentMethodID


class _BaseAck(BaseModel):
    success: bool
    message: str = Field(default=None)


class AckPaymentMethod(_BaseAck):
    ...


class SavedPaymentMethod(AckPaymentMethod):
    payment_method_id: PaymentMethodID


class AckPayment(_BaseAck):
    invoice_url: HttpUrl  # FIXME: ask Dennis what value do I get here if fails?
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
