from datetime import datetime
from decimal import Decimal

from models_library.resource_tracker import PricingDetailId, PricingPlanId
from pydantic import BaseModel


class PricingDetailDB(BaseModel):
    pricing_detail_id: PricingDetailId
    pricing_plan_id: PricingPlanId
    unit_name: str
    cost_per_unit: Decimal
    valid_from: datetime
    valid_to: datetime | None
    specific_info: dict
    created: datetime
    simcore_default: bool

    class Config:
        orm_mode = True
