from datetime import datetime
from typing import Any, NamedTuple, Self, cast

from models_library.basic_types import IDStr
from models_library.resource_tracker import PricingPlanId
from pydantic import BaseModel, ConfigDict, HttpUrl, PositiveInt
from pydantic.config import JsonDict

from ..licenses import (
    VIP_DETAILS_EXAMPLE,
    FeaturesDict,
    LicensedItem,
    LicensedItemID,
    LicensedResourceType,
)
from ._base import OutputSchema

# RPC


class LicensedItemRpcGet(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: dict[str, Any]
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "display_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "licensed_resource_data": cast(JsonDict, VIP_DETAILS_EXAMPLE),
                    "pricing_plan_id": "15",
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        },
    )


class LicensedItemRpcGetPage(NamedTuple):
    items: list[LicensedItemRpcGet]
    total: PositiveInt


# Rest


class _ItisVipRestData(BaseModel):
    description: str
    thumbnail: str
    features: FeaturesDict
    doi: str


class _ItisVipResourceRestData(OutputSchema):
    category_id: IDStr
    category_display: str
    source: _ItisVipRestData
    terms_of_use_url: HttpUrl | None = None


class LicensedItemRestGet(OutputSchema):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: _ItisVipResourceRestData
    pricing_plan_id: PricingPlanId

    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "display_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "licensed_resource_data": cast(JsonDict, VIP_DETAILS_EXAMPLE),
                    "pricing_plan_id": "15",
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        }
    )

    @classmethod
    def from_domain_model(cls, item: LicensedItem) -> Self:

        return cls.model_validate(
            {
                "licensed_item_id": item.licensed_item_id,
                "display_name": item.display_name,
                "licensed_resource_type": item.licensed_resource_type,
                "licensed_resource_data": item.licensed_resource_data,
                "pricing_plan_id": item.pricing_plan_id,
                "created_at": item.created_at,
                "modified_at": item.modified_at,
            }
        )


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
