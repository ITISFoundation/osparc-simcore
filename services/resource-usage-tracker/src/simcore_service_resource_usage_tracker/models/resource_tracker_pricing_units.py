from datetime import datetime
from decimal import Decimal
from typing import Any

from models_library.resource_tracker import (
    HardwareInfo,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)
from pydantic import BaseModel, validator


class PricingUnitsDB(BaseModel):
    pricing_unit_id: PricingUnitId
    pricing_plan_id: PricingPlanId
    unit_name: str
    unit_extra_info: dict
    default: bool
    specific_info: HardwareInfo
    created: datetime
    modified: datetime
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId

    class Config:
        orm_mode = True

    @validator("specific_info", pre=True)
    @classmethod
    def default_hardware_info_when_empty(cls, v) -> HardwareInfo | Any:
        if not v:
            return HardwareInfo(aws_ec2_instances=[])
        return v


# class PricingUnitWithCostCreate(BaseModel):
#     pricing_plan_id: PricingPlanId
#     pricing_plan_key: str
#     unit_name: str
#     unit_extra_info: dict
#     default: bool
#     specific_info: dict
#     cost_per_unit: Decimal
#     comment: str


# class PricingUnitCostUpdate:
#     pricing_plan_id: PricingPlanId
#     pricing_plan_key: str
#     cost_per_unit: Decimal
#     comment: str

# class PricingUnitWithCostUpdate(BaseModel):
#     pricing_unit_id: PricingUnitId
#     unit_name: str
#     unit_extra_info: dict
#     default: bool
#     specific_info: dict
#     pricing_unit_cost_update: None | PricingUnitCostUpdate
