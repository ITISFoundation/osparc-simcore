from typing import Any, ClassVar

from pydantic import Field

from ..basic_types import NonNegativeDecimal
from ._base import OutputSchema


class CreditPriceGet(OutputSchema):
    product_name: str
    usd_per_credit: NonNegativeDecimal | None = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"productName": "osparc", "usdPerCredit": None},
                {"productName": "osparc", "usdPerCredit": "10"},
            ]
        }
