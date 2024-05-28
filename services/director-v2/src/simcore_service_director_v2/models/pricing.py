from decimal import Decimal
from typing import Any, ClassVar

from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)
from pydantic import BaseModel


class PricingInfo(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    pricing_unit_cost_id: PricingUnitCostId
    pricing_unit_cost: Decimal

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "pricing_unit_id": 1,
                    "pricing_unit_cost_id": 1,
                    "pricing_unit_cost": Decimal(10),
                }
            ]
        }
