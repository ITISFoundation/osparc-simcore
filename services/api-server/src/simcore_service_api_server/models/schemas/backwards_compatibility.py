# Models added here "cover" models from within the deployment in order to restore backwards compatibility

from typing import Annotated

from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.product import (
    GetCreditPrice as _GetCreditPrice,
)
from models_library.basic_types import NonNegativeDecimal
from pydantic import Field, NonNegativeFloat, NonNegativeInt, PlainSerializer


class GetCreditPrice(OutputSchema):
    product_name: str
    usd_per_credit: Annotated[
        NonNegativeDecimal,
        PlainSerializer(float, return_type=NonNegativeFloat, when_used="json"),
    ] | None = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
    )
    min_payment_amount_usd: NonNegativeInt | None = Field(
        ...,
        description="Minimum amount (included) in USD that can be paid for this product"
        "Can be None if this product's price is UNDEFINED",
    )


assert set(GetCreditPrice.model_fields.keys()) == set(
    _GetCreditPrice.model_fields.keys()
)