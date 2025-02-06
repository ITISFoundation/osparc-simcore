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


class _ItisVipRestData(OutputSchema):
    id: int
    description: str
    thumbnail: str
    features: FeaturesDict  # NOTE: here there is a bit of coupling with domain model
    doi: str | None


class _ItisVipResourceRestData(OutputSchema):
    category_id: IDStr
    category_display: str
    category_icon: HttpUrl | None = None  # NOTE: Placeholder until provide @odeimaiz
    source: _ItisVipRestData
    terms_of_use_url: HttpUrl | None = None  # NOTE: Placeholder until provided @mguidon


class LicensedItemRestGet(OutputSchema):
    licensed_item_id: LicensedItemID
    display_name: str
    # NOTE: to put here a discriminator we have to embed it one more layer
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: _ItisVipResourceRestData
    pricing_plan_id: PricingPlanId

    created_at: datetime
    modified_at: datetime

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "licensedItemId": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                        "displayName": "my best model",
                        "licensedResourceType": f"{LicensedResourceType.VIP_MODEL}",
                        "licensedResourceData": cast(
                            JsonDict,
                            {
                                "categoryId": "HumanWholeBody",
                                "categoryDisplay": "Humans",
                                "source": {**VIP_DETAILS_EXAMPLE, "doi": doi},
                            },
                        ),
                        "pricingPlanId": "15",
                        "createdAt": "2024-12-12 09:59:26.422140",
                        "modifiedAt": "2024-12-12 09:59:26.422140",
                    }
                    for doi in ["10.1000/xyz123", None]
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)

    @classmethod
    def from_domain_model(cls, item: LicensedItem) -> Self:

        return cls.model_validate(
            {
                "licensed_item_id": item.licensed_item_id,
                "display_name": item.display_name,
                "licensed_resource_type": item.licensed_resource_type,
                "licensed_resource_data": {
                    **item.licensed_resource_data,
                },
                "pricing_plan_id": item.pricing_plan_id,
                "created_at": item.created_at,
                "modified_at": item.modified_at,
            }
        )


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
