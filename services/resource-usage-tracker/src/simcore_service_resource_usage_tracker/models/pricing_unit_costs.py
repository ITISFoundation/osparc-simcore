from datetime import datetime
from decimal import Decimal

from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)
from pydantic import BaseModel, ConfigDict


class PricingUnitCostsDB(BaseModel):
    pricing_unit_cost_id: PricingUnitCostId
    pricing_plan_id: PricingPlanId
    pricing_plan_key: str
    pricing_unit_id: PricingUnitId
    pricing_unit_name: str
    cost_per_unit: Decimal
    valid_from: datetime
    valid_to: datetime | None
    created: datetime
    comment: str | None
    modified: datetime
    model_config = ConfigDict(from_attributes=True)
