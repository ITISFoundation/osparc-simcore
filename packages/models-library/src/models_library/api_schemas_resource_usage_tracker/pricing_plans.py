from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

from models_library.resource_tracker import (
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
)
from pydantic import BaseModel


class PricingUnitGet(BaseModel):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_attributes: dict
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId
    default: bool
    specific_info: dict

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "pricing_unit_id": 1,
                    "unit_name": "SMALL",
                    "unit_attributes": {},
                    "current_cost_per_unit": 5.7,
                    "current_cost_per_unit_id": 1,
                    "default": True,
                    "specific_info": {},
                }
            ]
        }


class ServicePricingPlanGet(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet]

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
                    "pricing_units": [
                        PricingUnitGet.Config.schema_extra["examples"][0]
                    ],
                }
            ]
        }
