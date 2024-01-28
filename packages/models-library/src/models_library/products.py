from decimal import Decimal
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

ProductName: TypeAlias = str


class CreditResultGet(BaseModel):
    product_name: ProductName
    credit_amount: Decimal = Field(..., description="")
    model_config = ConfigDict()
