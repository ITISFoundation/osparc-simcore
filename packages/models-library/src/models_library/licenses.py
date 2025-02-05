from datetime import datetime
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .licensed_items import LicensedResourceType
from .products import ProductName
from .resource_tracker import PricingPlanId

LicenseID: TypeAlias = UUID


#
# DB
#


class LicenseDB(BaseModel):
    license_id: LicenseID
    display_name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    product_name: ProductName

    # states
    created: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True)


class LicenseUpdateDB(BaseModel):
    display_name: str | None = None
    pricing_plan_id: PricingPlanId | None = None


#
# License Domain
#


class License(BaseModel):
    license_id: LicenseID
    display_name: str
    licensed_resource_type: LicensedResourceType
    resources: list[dict]
    pricing_plan_id: PricingPlanId
    product_name: ProductName

    model_config = ConfigDict(from_attributes=True)
