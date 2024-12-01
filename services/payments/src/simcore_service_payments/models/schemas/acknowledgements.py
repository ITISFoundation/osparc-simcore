# mypy: disable-error-code=truthy-function
from typing import Annotated, Any

from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID
from models_library.basic_types import IDStr
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pydantic_core.core_schema import ValidationInfo


class _BaseAck(BaseModel):
    success: bool
    message: str | None = Field(default=None)


class _BaseAckPayment(_BaseAck):
    provider_payment_id: IDStr | None = Field(
        default=None,
        description="Payment ID from the provider (e.g. stripe payment ID)",
    )

    invoice_url: HttpUrl | None = Field(
        default=None, description="Link to invoice is required when success=true"
    )
    # NOTE: Why invoice_pdf, stripe_invoice_id and stripe_customer_id nullable? Currently, we are dependent on a third party that is making
    # some changes for us. Adding these fields has a slightly lower priority. If they do not manage it, it is still okay for us.
    invoice_pdf: HttpUrl | None = Field(default=None, description="Link to invoice PDF")
    stripe_invoice_id: IDStr | None = Field(
        default=None, description="Stripe invoice ID"
    )
    stripe_customer_id: IDStr | None = Field(
        default=None, description="Stripe customer ID"
    )


#
# ACK payment-methods
#


class AckPaymentMethod(_BaseAck):
    ...


class SavedPaymentMethod(AckPaymentMethod):
    payment_method_id: PaymentMethodID


#
# ACK payments
#

_ONE_TIME_SUCCESS: dict[str, Any] = {
    "success": True,
    "provider_payment_id": "pi_123ABC",
    "invoice_url": "https://invoices.com/id=12345",
}
_EXAMPLES: list[dict[str, Any]] = [
    # 0. one-time-payment successful
    _ONE_TIME_SUCCESS,
    # 1. one-time-payment and payment-method-saved successful
    {
        **_ONE_TIME_SUCCESS,
        "saved": {
            "success": True,
            "payment_method_id": "3FA85F64-5717-4562-B3FC-2C963F66AFA6",
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


class AckPayment(_BaseAckPayment):

    saved: SavedPaymentMethod | None = Field(
        default=None,
        description="Gets the payment-method if user opted to save it during payment."
        "If used did not opt to save of payment-method was already saved, then it defaults to None",
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": _EXAMPLES[1].copy(),  # shown in openapi.json
            "examples": _EXAMPLES,  # type:ignore[dict-item]
        }
    )

    @field_validator("invoice_url")
    @classmethod
    def success_requires_invoice(cls, v, info: ValidationInfo):
        success = info.data.get("success")
        if success and not v:
            msg = "Invoice required on successful payments"
            raise ValueError(msg)
        return v


class AckPaymentWithPaymentMethod(_BaseAckPayment):
    # NOTE: This model is equivalent to `AckPayment`, nonetheless
    # I decided to separate it for clarity in the OAS since in payments
    # w/ payment-method the field `saved` will never be provided,

    payment_id: Annotated[
        PaymentID | None, Field(description="Payment ID from the gateway")
    ] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **_ONE_TIME_SUCCESS,
                "payment_id": "D19EE68B-B007-4B61-A8BC-32B7115FB244",
            },  # shown in openapi.json
        }
    )


assert PaymentID  # nosec
assert PaymentMethodID  # nosec


__all__: tuple[str, ...] = (
    "PaymentID",
    "PaymentMethodID",
)
