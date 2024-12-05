from datetime import datetime
from typing import NamedTuple

from models_library.licensed_items import LicensedItemID, LicensedResourceType
from models_library.resource_tracker import PricingPlanId
from pydantic import PositiveInt

from ._base import OutputSchema


class LicensedItemGet(OutputSchema):
    licensed_item_id: LicensedItemID
    name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime


class LicensedItemGetPage(NamedTuple):
    items: list[LicensedItemGet]
    total: PositiveInt
