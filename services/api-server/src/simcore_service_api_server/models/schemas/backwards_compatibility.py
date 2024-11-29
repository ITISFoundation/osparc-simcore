# Models added here "cover" models from within the deployment in order to restore backwards compatibility

from typing import Annotated

from models_library.api_schemas_webserver.product import GetCreditPrice
from models_library.basic_types import NonNegativeDecimal
from pydantic import Field, NonNegativeFloat, PlainSerializer


class GetCreditPriceApiServer(GetCreditPrice):
    usd_per_credit: Annotated[
        NonNegativeDecimal,
        PlainSerializer(float, return_type=NonNegativeFloat, when_used="json"),
    ] | None = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
    )
