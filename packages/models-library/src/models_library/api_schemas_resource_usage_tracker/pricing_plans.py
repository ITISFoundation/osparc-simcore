from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ..resource_tracker import (
    HardwareInfo,
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)


class PricingUnitGet(BaseModel):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: dict
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId
    default: bool
    specific_info: HardwareInfo
    model_config = ConfigDict()


class ServicePricingPlanGet(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet]
    model_config = ConfigDict()
