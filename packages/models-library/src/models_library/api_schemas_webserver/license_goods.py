from datetime import datetime
from typing import NamedTuple

from models_library.license_goods import LicenseGoodID, LicenseResourceType
from models_library.resource_tracker import PricingPlanId
from pydantic import PositiveInt

from ._base import OutputSchema


class LicenseGoodGet(OutputSchema):
    license_good_id: LicenseGoodID
    name: str
    license_resource_type: LicenseResourceType
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime


class LicenseGoodGetPage(NamedTuple):
    items: list[LicenseGoodGet]
    total: PositiveInt
