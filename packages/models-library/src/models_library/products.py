from decimal import Decimal
from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field

ProductName: TypeAlias = str
StripePriceID: TypeAlias = str
StripeTaxRateID: TypeAlias = str


class CreditResultGet(BaseModel):
    product_name: ProductName
    credit_amount: Decimal = Field(..., description="")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"product_name": "s4l", "credit_amount": Decimal(15.5)},
            ]
        }


class ProductStripeInfoGet(BaseModel):
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "stripe_price_id": "stripe-price-id",
                    "stripe_tax_rate_id": "stripe-tax-rate-id",
                },
            ]
        }
