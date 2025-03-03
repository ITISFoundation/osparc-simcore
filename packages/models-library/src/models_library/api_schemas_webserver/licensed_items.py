from datetime import date, datetime
from typing import Literal, NamedTuple, NotRequired, Self, cast

from models_library.basic_types import IDStr
from models_library.resource_tracker import PricingPlanId
from pydantic import BaseModel, ConfigDict, HttpUrl, PositiveInt
from pydantic.config import JsonDict
from typing_extensions import TypedDict

from ..licenses import (
    VIP_DETAILS_EXAMPLE,
    FeaturesDict,
    LicensedItem,
    LicensedItemID,
    LicensedItemKey,
    LicensedItemVersion,
    LicensedResourceType,
)
from ._base import OutputSchema

# RPC


class LicensedResourceSourceFeaturesDict(TypedDict):
    age: NotRequired[str]
    date: date
    ethnicity: NotRequired[str]
    functionality: NotRequired[str]
    height: NotRequired[str]
    name: NotRequired[str]
    sex: NotRequired[str]
    species: NotRequired[str]
    version: NotRequired[str]
    weight: NotRequired[str]


class LicensedResourceSource(BaseModel):
    id: int
    description: str
    thumbnail: str
    features: LicensedResourceSourceFeaturesDict
    doi: str | None
    license_key: str
    license_version: str
    protection: Literal["Code", "PayPal"]
    available_from_url: HttpUrl | None


class LicensedResource(BaseModel):
    source: LicensedResourceSource
    category_id: IDStr
    category_display: str
    terms_of_use_url: HttpUrl | None = None


class LicensedItemRpcGet(BaseModel):
    licensed_item_id: LicensedItemID
    key: LicensedItemKey
    version: LicensedItemVersion
    display_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resources: list[LicensedResource]
    pricing_plan_id: PricingPlanId
    is_hidden_on_market: bool
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
                    "is_hidden_on_market": False,
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
    source: _ItisVipRestData


class LicensedItemRestGet(OutputSchema):
    licensed_item_id: LicensedItemID
    key: LicensedItemKey
    version: LicensedItemVersion

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
                    _ItisVipResourceRestData(**x) for x in item.licensed_resources
                ],
                "category_id": item.licensed_resources[0]["category_id"],
                "category_display": item.licensed_resources[0]["category_display"],
                "terms_of_use_url": item.licensed_resources[0].get(
                    "terms_of_use_url", None
                ),
            }
        )


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
