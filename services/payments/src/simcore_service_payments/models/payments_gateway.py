from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias
from uuid import UUID

from models_library.basic_types import NonEmptyStr, PositiveDecimal
from pydantic import BaseModel, EmailStr, Extra


class ErrorModel(BaseModel):
    message: str
    exception: str | None = None
    file: Path | str | None = None
    line: int | None = None
    trace: list | None = None


class InitPayment(BaseModel):
    amount_dollars: PositiveDecimal
    # metadata to store for billing or reference
    credits: PositiveDecimal
    user_name: NonEmptyStr
    user_email: EmailStr
    wallet_name: NonEmptyStr

    class Config:
        extra = Extra.forbid


PaymentID: TypeAlias = UUID


class PaymentInitiated(BaseModel):
    payment_id: PaymentID


PaymentMethodID: TypeAlias = UUID


class InitPaymentMethod(BaseModel):
    method: Literal["CC"] = "CC"
    # metadata to store for billing or reference
    user_name: NonEmptyStr
    user_email: EmailStr
    wallet_name: NonEmptyStr

    class Config:
        extra = Extra.forbid


class PaymentMethodInitiated(BaseModel):
    payment_method_id: PaymentMethodID


class GetPaymentMethod(BaseModel):
    idr: PaymentMethodID
    card_holder_name: str
    card_number_masked: str
    card_type: str
    expiration_month: int
    expiration_year: int
    street_address: str
    zipcode: str
    country: str
    created: datetime


class BatchGetPaymentMethods(BaseModel):
    payment_methods_ids: list[PaymentMethodID]


class PaymentMethodsBatch(BaseModel):
    items: list[GetPaymentMethod]
