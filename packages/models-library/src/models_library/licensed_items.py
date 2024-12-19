from datetime import datetime
from enum import auto
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .products import ProductName
from .resource_tracker import PricingPlanId
from .utils.enums import StrAutoEnum

LicensedItemID: TypeAlias = UUID


class LicensedResourceType(StrAutoEnum):
    VIP_MODEL = auto()


#
# DB
#


class LicensedItemDB(BaseModel):
    licensed_item_id: LicensedItemID
    name: str
    license_key: str | None
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    product_name: ProductName
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
    name: str | None = None
    pricing_plan_id: PricingPlanId | None = None
