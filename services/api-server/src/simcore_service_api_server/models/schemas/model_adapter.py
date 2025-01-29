# Models added here "cover" models from within the deployment in order to restore backwards compatibility

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from models_library.api_schemas_api_server.pricing_plans import (
    ServicePricingPlanGet as _ServicePricingPlanGet,
)
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemRpcGet as _LicensedItemGet,
)
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet as _LicensedItemCheckoutRpcGet,
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
from models_library.groups import GroupID
from models_library.licensed_items import (
    LicensedItemID,
    LicensedResourceType,
    VipDetails,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitId,
    UnitExtraInfo,
)
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.users import UserID
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
    model_config = ConfigDict(
        populate_by_name=True,
    )


assert set(GetCreditPriceLegacy.model_fields.keys()) == set(
    _GetCreditPrice.model_fields.keys()
)


class PricingUnitGetLegacy(BaseModel):
    pricing_unit_id: PricingUnitId = Field(alias="pricingUnitId")
    unit_name: str = Field(alias="unitName")
    unit_extra_info: UnitExtraInfo = Field(alias="unitExtraInfo")
    current_cost_per_unit: Annotated[
        Decimal, PlainSerializer(float, return_type=NonNegativeFloat, when_used="json")
    ] = Field(alias="currentCostPerUnit")
    default: bool
    model_config = ConfigDict(
        populate_by_name=True,
    )


assert set(PricingUnitGetLegacy.model_fields.keys()) == set(
    _PricingUnitGet.model_fields.keys()
)


class WalletGetWithAvailableCreditsLegacy(BaseModel):
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
    model_config = ConfigDict(
        populate_by_name=True,
    )


assert set(WalletGetWithAvailableCreditsLegacy.model_fields.keys()) == set(
    _WalletGetWithAvailableCredits.model_fields.keys()
)


class ServicePricingPlanGetLegacy(BaseModel):
    pricing_plan_id: PricingPlanId = Field(alias="pricingPlanId")
    display_name: str = Field(alias="displayName")
    description: str
    classification: PricingPlanClassification
    created_at: datetime = Field(alias="createdAt")
    pricing_plan_key: str = Field(alias="pricingPlanKey")
    pricing_units: list[PricingUnitGetLegacy] = Field(alias="pricingUnits")
    model_config = ConfigDict(
        populate_by_name=True,
    )


assert set(ServicePricingPlanGetLegacy.model_fields.keys()) == set(
    _ServicePricingPlanGet.model_fields.keys()
)


class LicensedItemGet(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: Annotated[str, Field(alias="display_name")]
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    licensed_resource_type_details: VipDetails
    created_at: datetime
    modified_at: datetime
    model_config = ConfigDict(
        populate_by_name=True,
    )


assert set(LicensedItemGet.model_fields.keys()) == set(
    _LicensedItemGet.model_fields.keys()
)


class LicensedItemCheckoutGet(BaseModel):
    licensed_item_checkout_id: LicensedItemCheckoutID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    product_name: ProductName
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int


assert set(LicensedItemCheckoutGet.model_fields.keys()) == set(
    _LicensedItemCheckoutRpcGet.model_fields.keys()
)
