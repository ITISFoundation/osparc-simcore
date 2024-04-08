from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel

from ..resource_tracker import (
    HardwareInfo,
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    UnitExtraInfo,
)


class PricingUnitGet(BaseModel):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId
    default: bool
    specific_info: HardwareInfo

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "pricing_unit_id": 1,
                    "unit_name": "SMALL",
                    "unit_extra_info": UnitExtraInfo.Config.schema_extra["examples"][0],
                    "current_cost_per_unit": 5.7,
                    "current_cost_per_unit_id": 1,
                    "default": True,
                    "specific_info": hw_config_example,
                }
                for hw_config_example in HardwareInfo.Config.schema_extra["examples"]
            ]
        }


class PricingPlanGet(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet] | None
    is_active: bool

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "display_name": "Pricing Plan for Sleeper",
                    "description": "Special Pricing Plan for Sleeper",
                    "classification": "TIER",
                    "created_at": "2023-01-11 13:11:47.293595",
                    "pricing_plan_key": "pricing-plan-sleeper",
                    "pricing_units": [pricing_unit_get_example],
                    "is_active": True,
                }
                for pricing_unit_get_example in PricingUnitGet.Config.schema_extra[
                    "examples"
                ]
            ]
        }


class PricingPlanToServiceGet(BaseModel):
    pricing_plan_id: PricingPlanId
    service_key: ServiceKey
    service_version: ServiceVersion
    created: datetime

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "service_key": "simcore/services/comp/itis/sleeper",
                    "service_version": "2.0.2",
                    "created": "2023-01-11 13:11:47.293595",
                }
            ]
        }
