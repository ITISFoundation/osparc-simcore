from decimal import Decimal

from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)
from pydantic import BaseModel, ConfigDict


class PricingInfo(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    pricing_unit_cost_id: PricingUnitCostId
    pricing_unit_cost: Decimal

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "pricing_unit_id": 1,
                    "pricing_unit_cost_id": 1,
                    "pricing_unit_cost": Decimal(10),  # type: ignore[dict-item]
                }
            ]
        }
    )
