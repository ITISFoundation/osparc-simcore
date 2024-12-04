from datetime import datetime
from enum import auto
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from .products import ProductName
from .resource_tracker import PricingPlanId
from .utils.enums import StrAutoEnum

LicenseGoodID: TypeAlias = PositiveInt


class LicenseResourceType(StrAutoEnum):
    VIP_MODEL = auto()


#
# DB
#


class LicenseGoodDB(BaseModel):
    license_good_id: LicenseGoodID
    name: str
    license_resource_type: LicenseResourceType
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


class LicenseGoodUpdateDB(BaseModel):
    name: str | None = None
    pricing_plan_id: PricingPlanId | None = None
