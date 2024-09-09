from decimal import Decimal
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

ProductName: TypeAlias = str
StripePriceID: TypeAlias = str
StripeTaxRateID: TypeAlias = str


class CreditResultGet(BaseModel):
    product_name: ProductName
    credit_amount: Decimal = Field(..., description="")
    model_config = ConfigDict()


class ProductStripeInfoGet(BaseModel):
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID
    model_config = ConfigDict()
