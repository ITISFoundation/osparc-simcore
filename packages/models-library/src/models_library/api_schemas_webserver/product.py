from decimal import Decimal

from pydantic import validator

from ._base import OutputSchema


class ProductPriceGet(OutputSchema):
    product_name: str
    dollars_per_credit: Decimal

    @validator("dollars_per_credit")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            msg = "Must be non-negative value, got {v}"
            raise ValueError(msg)
        return v
