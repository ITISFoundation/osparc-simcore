from decimal import Decimal
from typing import Any, ClassVar

from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, validator

from .products import StripePriceID, StripeTaxRateID


class UserInvoiceAddress(BaseModel):
    line1: str | None = None
    state: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str = Field(
        ...,
        description="Currently validated in webserver via pycountry library. Two letter country code alpha_2 expected.",
    )

    @validator("*", pre=True)
    @classmethod
    def parse_empty_string_as_null(cls, v):
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
        return v

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
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


class InvoiceDataGet(BaseModel):
    credit_amount: Decimal
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID
    user_invoice_address: UserInvoiceAddress
    user_name: str
    user_email: LowerCaseEmailStr

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "credit_amount": Decimal(15.5),
                    "stripe_price_id": "stripe-price-id",
                    "stripe_tax_rate_id": "stripe-tax-rate-id",
                    "user_invoice_address": UserInvoiceAddress.Config.schema_extra[
                        "examples"
                    ][0],
                    "user_name": "My Name",
                    "user_email": LowerCaseEmailStr("email@example.itis"),
                },
            ]
        }
