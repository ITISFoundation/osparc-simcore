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
    key: str
    version: str
    display_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resources: list[dict[str, Any]]
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "key": "Duke",
                    "version": "1.0.0",
                    "display_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "licensed_resources": [cast(JsonDict, VIP_DETAILS_EXAMPLE)],
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
    license_version: str


class _ItisVipResourceRestData(OutputSchema):
    # category_id: IDStr
    # category_display: str
    # category_icon: HttpUrl | None = None  # NOTE: Placeholder until provide @odeimaiz
    source: _ItisVipRestData
    # terms_of_use_url: HttpUrl | None = None  # NOTE: Placeholder until provided @mguidon


class LicensedItemRestGet(OutputSchema):
    licensed_item_id: LicensedItemID
    key: str
    version: str

    display_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resources: list[_ItisVipResourceRestData]
    pricing_plan_id: PricingPlanId

    category_id: IDStr
    category_display: str
    category_icon: HttpUrl | None = None  # NOTE: Placeholder until provide @odeimaiz
    terms_of_use_url: HttpUrl | None = None  # NOTE: Placeholder until provided @mguidon

    created_at: datetime
    modified_at: datetime

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "licensedItemId": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                        "key": "Duke",
                        "version": "1.0.0",
                        "displayName": "my best model",
                        "licensedResourceType": f"{LicensedResourceType.VIP_MODEL}",
                        "licensedResources": [
                            cast(
                                JsonDict,
                                {
                                    "source": {**VIP_DETAILS_EXAMPLE, "doi": doi},
                                },
                            )
                        ],
                        "pricingPlanId": "15",
                        "categoryId": "HumanWholeBody",
                        "categoryDisplay": "Humans",
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
                **item.model_dump(
                    include={
                        "licensed_item_id",
                        "key",
                        "version",
                        "display_name",
                        "licensed_resource_type",
                        "pricing_plan_id",
                        "created_at",
                        "modified_at",
                    },
                    exclude_unset=True,
                ),
                "licensed_resources": [
                    _ItisVipResourceRestData(**x)
                    for x in item.array_of_licensed_resource_data
                ],
                "category_id": item.array_of_licensed_resource_data[0]["category_id"],
                "category_display": item.array_of_licensed_resource_data[0][
                    "category_display"
                ],
            }
        )


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
