from datetime import datetime
from enum import auto
from typing import Any, NamedTuple, NotRequired, TypeAlias, cast
from uuid import UUID

from models_library.resource_tracker import PricingPlanId
from pydantic import BaseModel, ConfigDict, PositiveInt
from pydantic.config import JsonDict
from typing_extensions import TypedDict

from .products import ProductName
from .resource_tracker import PricingPlanId
from .utils.enums import StrAutoEnum

LicensedItemID: TypeAlias = UUID
LicenseID: TypeAlias = UUID
LicensedResourceID: TypeAlias = UUID


class LicensedResourceType(StrAutoEnum):
    VIP_MODEL = auto()


VIP_FEATURES_EXAMPLE = {
    "name": "Duke",
    "version": "V2.0",
    "sex": "Male",
    "age": "34 years",
    "weight": "70.2 Kg",
    "height": "1.77 m",
    "date": "2015-03-01",
    "ethnicity": "Caucasian",
    "functionality": "Static",
    "additional_field": "allowed",
}


class FeaturesDict(TypedDict):
    name: NotRequired[str]
    version: NotRequired[str]
    sex: NotRequired[str]
    age: NotRequired[str]
    weight: NotRequired[str]
    height: NotRequired[str]
    date: str
    ethnicity: NotRequired[str]
    functionality: NotRequired[str]


VIP_DETAILS_EXAMPLE = {
    "id": 1,
    "description": "A detailed description of the VIP model",
    "thumbnail": "https://example.com/thumbnail.jpg",
    "features": VIP_FEATURES_EXAMPLE,
    "doi": "10.1000/xyz123",
    "license_key": "ABC123XYZ",
    "license_version": "1.0",
    "protection": "Code",
    "available_from_url": "https://example.com/download",
    "additional_field": "trimmed if rest",
}


#
# DB
#


class LicensedItemDB(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str

    licensed_resource_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: dict[str, Any] | None

    pricing_plan_id: PricingPlanId | None
    product_name: ProductName | None

    # states
    created: datetime
    modified: datetime
    trashed: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LicensedItemUpdateDB(BaseModel):
    display_name: str | None = None
    licensed_resource_name: str | None = None
    pricing_plan_id: PricingPlanId | None = None
    trash: bool | None = None


class LicensedItem(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: dict[str, Any]
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                        "display_name": "my best model",
                        "licensed_resource_name": "best-model",
                        "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                        "licensed_resource_data": cast(
                            JsonDict,
                            {
                                "category_id": "HumanWholeBody",
                                "category_display": "Humans",
                                "source": VIP_DETAILS_EXAMPLE,
                            },
                        ),
                        "pricing_plan_id": "15",
                        "created_at": "2024-12-12 09:59:26.422140",
                        "modified_at": "2024-12-12 09:59:26.422140",
                    }
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class LicensedItemPage(NamedTuple):
    total: PositiveInt
    items: list[LicensedItem]
