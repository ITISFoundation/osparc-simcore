from decimal import Decimal
from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field

ProductName: TypeAlias = str


class CreditResultGet(BaseModel):
    product_name: ProductName
    credit_amount: Decimal = Field(..., description="")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"product_name": "s4l", "credit_amount": Decimal(15.5)},
            ]
        }
