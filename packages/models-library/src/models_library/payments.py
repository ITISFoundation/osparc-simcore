from decimal import Decimal
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .emails import LowerCaseEmailStr
from .products import StripePriceID, StripeTaxRateID

StripeInvoiceID: TypeAlias = str


class UserInvoiceAddress(BaseModel):
    line1: str | None = None
    state: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str = Field(
        ...,
        description="Currently validated in webserver via pycountry library. Two letter country code alpha_2 expected.",
    )

    @field_validator("*", mode="before")
    @classmethod
    @classmethod
    def parse_empty_string_as_null(cls, v):
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
        return v

    model_config = ConfigDict()


class InvoiceDataGet(BaseModel):
    credit_amount: Decimal
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID
    user_invoice_address: UserInvoiceAddress
    user_display_name: str
    user_email: LowerCaseEmailStr
    model_config = ConfigDict()
