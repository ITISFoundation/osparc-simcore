from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID
from models_library.basic_types import AmountDecimal, IDStr
from models_library.payments import UserInvoiceAddress
from models_library.products import StripePriceID, StripeTaxRateID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

COUNTRIES_WITH_VAT = ["CH", "LI"]


class ErrorModel(BaseModel):
    message: str
    exception: str | None = None
    file: Path | str | None = None
    line: int | None = None
    trace: list | None = None


class StripeTaxExempt(str, Enum):
    exempt = "exempt"
    none = "none"  # <-- if customer is from CH or LI
    reverse = "reverse"  # <-- if customer is outside of CH or LI


class InitPayment(BaseModel):
    amount_dollars: AmountDecimal
    # metadata to store for billing or reference
    credits_: AmountDecimal = Field(
        ...,
        alias="credits",
        json_schema_extra={"describe": "This is equal to `quantity` field in Stripe"},
    )
    user_name: IDStr
    user_email: EmailStr
    user_address: UserInvoiceAddress
    wallet_name: IDStr
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID
    stripe_tax_exempt_value: StripeTaxExempt
    model_config = ConfigDict(extra="forbid")


class PaymentInitiated(BaseModel):
    payment_id: PaymentID


class PaymentCancelled(BaseModel):
    message: str | None = None


class InitPaymentMethod(BaseModel):
    method: Literal["CC"] = "CC"
    # metadata to store for billing or reference
    user_name: IDStr
    user_email: EmailStr
    wallet_name: IDStr
    model_config = ConfigDict(extra="forbid")


class PaymentMethodInitiated(BaseModel):
    payment_method_id: PaymentMethodID


class GetPaymentMethod(BaseModel):
    id: PaymentMethodID
    card_holder_name: str | None = None
    card_number_masked: str | None = None
    card_type: str | None = None
    expiration_month: int | None = None
    expiration_year: int | None = None
    created: datetime


class BatchGetPaymentMethods(BaseModel):
    payment_methods_ids: list[PaymentMethodID]


class PaymentMethodsBatch(BaseModel):
    items: list[GetPaymentMethod]
