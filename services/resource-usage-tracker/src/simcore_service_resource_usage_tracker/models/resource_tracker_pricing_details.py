from datetime import datetime

from models_library.resource_tracker import PricingDetailId, PricingPlanId
from pydantic import BaseModel


class PricingDetailDB(BaseModel):
    pricing_detail_id: PricingDetailId
    pricing_plan_id: PricingPlanId
    unit_name: str
    cost_per_unit: float
    valid_from: datetime
    valid_to: datetime | None
    specific_info: dict
    created: datetime

    class Config:
        orm_mode = True
