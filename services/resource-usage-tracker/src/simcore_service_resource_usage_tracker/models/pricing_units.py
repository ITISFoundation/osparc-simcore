from datetime import datetime
from decimal import Decimal
from typing import Any

from models_library.resource_tracker import (
    HardwareInfo,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    UnitExtraInfo,
)
from pydantic import BaseModel, ConfigDict, field_validator


class PricingUnitsDB(BaseModel):
    pricing_unit_id: PricingUnitId
    pricing_plan_id: PricingPlanId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    default: bool
    specific_info: HardwareInfo
    created: datetime
    modified: datetime
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId
    model_config = ConfigDict(from_attributes=True)

    @field_validator("specific_info", mode="before")
    @classmethod
    def default_hardware_info_when_empty(cls, v) -> HardwareInfo | Any:
        if not v:
            return HardwareInfo(aws_ec2_instances=[])
        return v
