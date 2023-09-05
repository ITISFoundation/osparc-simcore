from pydantic import BaseModel, Field

from ..payments_gateway import PaymentID, PaymentMethodID


class _BaseAck(BaseModel):
    success: bool
    message: str = Field(default=None)


class AckPayment(_BaseAck):
    ...


class AckPaymentMethod(BaseModel):
    ...


assert PaymentID  # nosec
assert PaymentMethodID  # nosec
__all__: tuple[str, ...] = (
    "PaymentID",
    "PaymentMethodID",
)
