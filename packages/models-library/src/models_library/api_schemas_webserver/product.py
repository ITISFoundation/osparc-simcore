from decimal import Decimal
from typing import Any, ClassVar

from pydantic import Field, validator

from ._base import OutputSchema


class ProductPriceGet(OutputSchema):
    product_name: str
    dollars_per_credit: Decimal | None = Field(
        ...,
        description="Price of a credit in dollars. "
        "If None, then this product's price is UNDEFINED",
    )

    @validator("dollars_per_credit")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            msg = "Must be non-negative value, got {v}"
            raise ValueError(msg)
        return v

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"productName": "osparc", "dollarsPerCredit": "null"},
                {"productName": "osparc", "dollarsPerCredit": "10"},
            ]
        }
