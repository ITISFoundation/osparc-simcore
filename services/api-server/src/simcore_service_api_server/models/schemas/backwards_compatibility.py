# Models added here "cover" models from within the deployment in order to restore backwards compatibility

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from models_library.api_schemas_api_server.pricing_plans import (
    ServicePricingPlanGet as _ServicePricingPlanGet,
)
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.product import (
    GetCreditPrice as _GetCreditPrice,
)
from models_library.api_schemas_webserver.resource_usage import (
    PricingUnitGet as _PricingUnitGet,
)
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.api_schemas_webserver.wallets import (
    WalletGetWithAvailableCredits as _WalletGetWithAvailableCredits,
)
from models_library.basic_types import NonNegativeDecimal
from models_library.resource_tracker import (
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitId,
    UnitExtraInfo,
)
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


class PricingUnitGet(OutputSchema):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    current_cost_per_unit: Annotated[
        Decimal, PlainSerializer(float, return_type=NonNegativeFloat, when_used="json")
    ]
    default: bool


assert set(PricingUnitGet.model_fields.keys()) == set(
    _PricingUnitGet.model_fields.keys()
)


class WalletGetWithAvailableCredits(WalletGet):
    available_credits: Annotated[
        Decimal, PlainSerializer(float, return_type=NonNegativeFloat, when_used="json")
    ]


assert set(WalletGetWithAvailableCredits.model_fields.keys()) == set(
    _WalletGetWithAvailableCredits.model_fields.keys()
)


class ServicePricingPlanGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet]


assert set(ServicePricingPlanGet.model_fields.keys()) == set(
    _ServicePricingPlanGet.model_fields.keys()
)
