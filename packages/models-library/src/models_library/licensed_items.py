from datetime import datetime
from enum import auto
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    product_name: ProductName
    licensed_resource_type_details: dict[str, Any]
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp of last modification",
    )
    # ----
    model_config = ConfigDict(from_attributes=True)


class LicensedItemUpdateDB(BaseModel):
    display_name: str | None = None
    pricing_plan_id: PricingPlanId | None = None
