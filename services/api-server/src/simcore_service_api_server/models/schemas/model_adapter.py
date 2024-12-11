# Models added here "cover" models from within the deployment in order to restore backwards compatibility

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from models_library.api_schemas_api_server.pricing_plans import (
    ServicePricingPlanGet as _ServicePricingPlanGet,
)
from models_library.api_schemas_webserver.product import (
    GetCreditPrice as _GetCreditPrice,
)
from models_library.api_schemas_webserver.resource_usage import (
    PricingUnitGet as _PricingUnitGet,
)
from models_library.api_schemas_webserver.wallets import (
    WalletGetWithAvailableCredits as _WalletGetWithAvailableCredits,
)
from models_library.basic_types import IDStr, NonNegativeDecimal
from models_library.resource_tracker import (
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitId,
    UnitExtraInfo,
)
from models_library.users import GroupID
from models_library.wallets import WalletID, WalletStatus
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PlainSerializer,
)


class GetCreditPriceLegacy(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    product_name: str = Field(alias="productName")
    usd_per_credit: (
        Annotated[
            NonNegativeDecimal,
            PlainSerializer(float, return_type=NonNegativeFloat, when_used="json"),
        ]
        | None
    ) = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
        alias="usdPerCredit",
    )
    min_payment_amount_usd: NonNegativeInt | None = Field(
        ...,
        description="Minimum amount (included) in USD that can be paid for this product"
        "Can be None if this product's price is UNDEFINED",
        alias="minPaymentAmountUsd",
    )


assert set(GetCreditPriceLegacy.model_fields.keys()) == set(
    _GetCreditPrice.model_fields.keys()
)


class PricingUnitGetLegacy(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    pricing_unit_id: PricingUnitId = Field(alias="pricingUnitId")
    unit_name: str = Field(alias="unitName")
    unit_extra_info: UnitExtraInfo = Field(alias="unitExtraInfo")
    current_cost_per_unit: Annotated[
        Decimal, PlainSerializer(float, return_type=NonNegativeFloat, when_used="json")
    ] = Field(alias="currentCostPerUnit")
    default: bool


assert set(PricingUnitGetLegacy.model_fields.keys()) == set(
    _PricingUnitGet.model_fields.keys()
)


class WalletGetWithAvailableCreditsLegacy(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    wallet_id: WalletID = Field(alias="walletId")
    name: IDStr
    description: str | None = None
    owner: GroupID
    thumbnail: str | None = None
    status: WalletStatus
    created: datetime
    modified: datetime
    available_credits: Annotated[
        Decimal, PlainSerializer(float, return_type=NonNegativeFloat, when_used="json")
    ] = Field(alias="availableCredits")


assert set(WalletGetWithAvailableCreditsLegacy.model_fields.keys()) == set(
    _WalletGetWithAvailableCredits.model_fields.keys()
)


class ServicePricingPlanGetLegacy(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    pricing_plan_id: PricingPlanId = Field(alias="pricingPlanId")
    display_name: str = Field(alias="displayName")
    description: str
    classification: PricingPlanClassification
    created_at: datetime = Field(alias="createdAt")
    pricing_plan_key: str = Field(alias="pricingPlanKey")
    pricing_units: list[PricingUnitGetLegacy] = Field(alias="pricingUnits")


assert set(ServicePricingPlanGetLegacy.model_fields.keys()) == set(
    _ServicePricingPlanGet.model_fields.keys()
)
