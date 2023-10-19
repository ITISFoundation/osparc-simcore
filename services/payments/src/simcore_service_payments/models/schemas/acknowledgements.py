from typing import Any, ClassVar

from pydantic import BaseModel, Field, HttpUrl, validator

from ..payments_gateway import PaymentID, PaymentMethodID


class _BaseAck(BaseModel):
    success: bool
    message: str = Field(default=None)


class AckPaymentMethod(_BaseAck):
    ...


class SavedPaymentMethod(AckPaymentMethod):
    payment_method_id: PaymentMethodID


_ONE_TIME_SUCCESS = {
    "success": True,
    "invoice_url": "https://invoices.com/id=12345",
}
_EXAMPLES = [
    # 0. one-time-payment successful
    _ONE_TIME_SUCCESS,
    # 1. one-time-payment and payment-method-saved successful
    {
        **_ONE_TIME_SUCCESS,
        "saved": {
            "success": True,
            "payment_method_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        },
    },
    # 2. one-time-payment successful but payment-method-saved failed
    {
        **_ONE_TIME_SUCCESS,
        "saved": {
            "success": False,
            "message": "Not allowed",
        },
    },
    # 3. one-time-payment failure
    {
        "success": False,
        "message": "No more credit",
    },
]


class AckPayment(_BaseAck):
    invoice_url: HttpUrl | None = Field(
        default=None, description="Link to invoice is required when success=true"
    )
    saved: SavedPaymentMethod | None = Field(
        default=None,
        description="If the user decided to save the payment method"
        "after payment it returns the payment-method acknoledgement response."
        "Otherwise it defaults to None.",
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": _EXAMPLES[1],  # shown in openapi.json
            "examples": _EXAMPLES,
        }

    @validator("invoice_url")
    @classmethod
    def success_requires_invoice(cls, v, values):
        success = values.get("success")
        invoice_url = v
        if success and not invoice_url:
            msg = "Invoice required on successful payments"
            raise ValueError(msg)


assert PaymentID  # nosec
assert PaymentMethodID  # nosec


__all__: tuple[str, ...] = (
    "PaymentID",
    "PaymentMethodID",
)
