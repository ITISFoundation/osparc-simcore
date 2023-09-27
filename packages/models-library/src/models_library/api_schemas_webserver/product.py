from datetime import datetime
from typing import Any, ClassVar

from models_library.products import ProductName
from pydantic import Field, HttpUrl

from ..basic_types import NonNegativeDecimal
from ..emails import LowerCaseEmailStr
from ._base import InputSchema, OutputSchema


class CreditPriceGet(OutputSchema):
    product_name: str
    usd_per_credit: NonNegativeDecimal | None = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"productName": "osparc", "usdPerCredit": None},
                {"productName": "osparc", "usdPerCredit": "10"},
            ]
        }


class GenerateInvitation(InputSchema):
    guest: LowerCaseEmailStr
    trial_account_days: int | None = None


class ProductInvitation(OutputSchema):
    product_name: ProductName
    issuer: LowerCaseEmailStr
    guest: LowerCaseEmailStr
    trial_account_days: int | None = None
    created: datetime
    invitation_url: HttpUrl

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "product_name": "osparc",
                    "issuer": "John Doe",
                    "guest": "guest@example.com",
                    "trial_account_days": 7,
                    "created": "2023-09-27T15:30:00",
                    "invitation_url": "https://example.com/invitation#1234",
                },
                {
                    "product_name": "osparc",
                    "issuer": "John Doe",
                    "guest": "guest@example.com",
                    "created": "2023-09-27T15:30:00",
                    "invitation_url": "https://example.com/invitation",
                },
            ]
        }
