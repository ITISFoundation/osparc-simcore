from datetime import datetime
from enum import auto
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .products import ProductName
from .resource_tracker import PricingPlanId
from .utils.enums import StrAutoEnum

LicensedItemID: TypeAlias = UUID


class LicensedResourceType(StrAutoEnum):
    VIP_MODEL = auto()


VIP_FEAUTES_EXAMPLE = {
    "name": "Duke",
    "version": "V2.0",
    "sex": "Male",
    "age": "34 years",
    "weight": "70.2 Kg",
    "height": "1.77 m",
    "data": "2015-03-01",
    "ethnicity": "Caucasian",
    "functionality": "Static",
    "additional_field": "allowed",
}

VIP_DETAILS_EXAMPLE = {
    "id": 1,
    "description": "custom description",
    "thumbnail": "custom description",
    "features": VIP_FEAUTES_EXAMPLE,
    "doi": "custom value",
    "license_key": "custom value",
    "license_version": "custom value",
    "protection": "custom value",
    "available_from_url": "custom value",
    "additional_field": "allowed",
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
