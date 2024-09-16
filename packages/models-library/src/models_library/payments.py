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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "line1": None,
                    "state": None,
                    "postal_code": None,
                    "city": None,
                    "country": "CH",
                },
            ]
        }
    )

    @field_validator("*", mode="before")
    @classmethod
    def parse_empty_string_as_null(cls, v):
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
        return v


class InvoiceDataGet(BaseModel):
    credit_amount: Decimal
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID
    user_invoice_address: UserInvoiceAddress
    user_display_name: str
    user_email: LowerCaseEmailStr

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "credit_amount": Decimal(15.5),  # type: ignore[dict-item]
                    "stripe_price_id": "stripe-price-id",
                    "stripe_tax_rate_id": "stripe-tax-rate-id",
                    "user_invoice_address": UserInvoiceAddress.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "user_display_name": "My Name",
                    "user_email": "email@example.itis",
                },
            ]
        }
    )
