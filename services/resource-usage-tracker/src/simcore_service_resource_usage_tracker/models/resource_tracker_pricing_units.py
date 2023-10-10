from datetime import datetime
from decimal import Decimal

from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)
from pydantic import BaseModel


class PricingUnitsDB(BaseModel):
    pricing_unit_id: PricingUnitId
    pricing_plan_id: PricingPlanId
    unit_name: str
    unit_extra_info: dict
    default: bool
    specific_info: dict
    created: datetime
    modified: datetime
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId

    class Config:
        orm_mode = True
