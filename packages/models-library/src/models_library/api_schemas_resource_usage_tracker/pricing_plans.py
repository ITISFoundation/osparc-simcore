from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ..resource_tracker import (
    HardwareInfo,
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    UnitExtraInfo,
)
from ..services_types import ServiceKey, ServiceVersion


class PricingUnitGet(BaseModel):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId
    default: bool
    specific_info: HardwareInfo
    model_config = ConfigDict()


class PricingPlanGet(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet] | None = None
    is_active: bool
    model_config = ConfigDict()


class PricingPlanToServiceGet(BaseModel):
    pricing_plan_id: PricingPlanId
    service_key: ServiceKey
    service_version: ServiceVersion
    created: datetime
    model_config = ConfigDict()
