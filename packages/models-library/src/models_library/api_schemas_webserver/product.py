from decimal import Decimal
from typing import Any, ClassVar

from pydantic import Field, validator

from ._base import OutputSchema


class ProductPriceGet(OutputSchema):
    product_name: str
    usd_per_credit: Decimal | None = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
    )

    @validator("usd_per_credit")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            msg = "Must be non-negative value, got {v}"
            raise ValueError(msg)
        return v

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"productName": "osparc", "usdPerCredit": "null"},
                {"productName": "osparc", "usdPerCredit": "10"},
            ]
        }
