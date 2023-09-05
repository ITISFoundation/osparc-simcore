import datetime
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel


class InitPayment(BaseModel):
    amount_dollars: Decimal
    # metadata to store for billing or reference
    credits: Decimal
    user_name: str
    user_email: str
    wallet_name: str


PaymentID: TypeAlias = UUID


class PaymentInitiated(BaseModel):
    payment_id: PaymentID


PaymentMethodID: TypeAlias = UUID


class InitPaymentMethod(BaseModel):
    method: Literal["CC"] = "CC"
    # metadata to store for billing or reference
    user_name: str
    user_email: str
    wallet_name: str


class PaymentMethodInitiated(BaseModel):
    payment_method_id: PaymentMethodID


class GetPaymentMethod(BaseModel):
    idr: PaymentMethodID
    card_holder_name: str
    card_number_masked: str
    card_type: str
    date_created: datetime
    expiration_month: int
    expiration_year: int
