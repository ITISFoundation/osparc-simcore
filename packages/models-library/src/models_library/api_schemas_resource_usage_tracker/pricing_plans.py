from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, PositiveInt, model_validator

from ..resource_tracker import (
    HardwareInfo,
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    UnitExtraInfoLicense,
    UnitExtraInfoTier,
)
from ..services_types import ServiceKey, ServiceVersion


class RutPricingUnitGet(BaseModel):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: UnitExtraInfoTier | UnitExtraInfoLicense
    current_cost_per_unit: Decimal
    current_cost_per_unit_id: PricingUnitCostId
    default: bool
    specific_info: HardwareInfo

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_unit_id": 1,
                    "unit_name": "SMALL",
                    "unit_extra_info": UnitExtraInfoTier.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "current_cost_per_unit": 5.7,
                    "current_cost_per_unit_id": 1,
                    "default": True,
                    "specific_info": hw_config_example,
                }
                for hw_config_example in HardwareInfo.model_config["json_schema_extra"][  # type: ignore[index,union-attr]
                    "examples"
                ]
            ]
            + [
                {
                    "pricing_unit_id": 2,
                    "unit_name": "5 seats",
                    "unit_extra_info": UnitExtraInfoLicense.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "current_cost_per_unit": 10.5,
                    "current_cost_per_unit_id": 2,
                    "default": False,
                    "specific_info": HardwareInfo.model_config["json_schema_extra"][  # type: ignore[index,union-attr]
                        "examples"
                    ][
                        1
                    ],
                }
            ]
        }
    )


class RutPricingPlanGet(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[RutPricingUnitGet] | None
    is_active: bool

    @model_validator(mode="after")
    def ensure_classification_matches_extra_info(self):
        """Enforce that all PricingUnitGet.unit_extra_info match the plan's classification."""
        if not self.pricing_units:
            return self  # No units to check

        for unit in self.pricing_units:
            if (
                self.classification == PricingPlanClassification.TIER
                and not isinstance(unit.unit_extra_info, UnitExtraInfoTier)
            ):
                error_message = (
                    "For TIER classification, unit_extra_info must be UnitExtraInfoTier"
                )
                raise ValueError(error_message)
            if (
                self.classification == PricingPlanClassification.LICENSE
                and not isinstance(unit.unit_extra_info, UnitExtraInfoLicense)
            ):
                error_message = "For LICENSE classification, unit_extra_info must be UnitExtraInfoLicense"
                raise ValueError(error_message)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "display_name": "Pricing Plan for Sleeper",
                    "description": "Special Pricing Plan for Sleeper",
                    "classification": "TIER",
                    "created_at": "2023-01-11 13:11:47.293595",
                    "pricing_plan_key": "pricing-plan-sleeper",
                    "pricing_units": [
                        RutPricingUnitGet.model_config["json_schema_extra"]["examples"][
                            0
                        ]
                    ],
                    "is_active": True,
                },
                {
                    "pricing_plan_id": 2,
                    "display_name": "VIP model A",
                    "description": "Special Pricing Plan for VIP",
                    "classification": "LICENSE",
                    "created_at": "2023-01-11 13:11:47.293595",
                    "pricing_plan_key": "vip-model-a",
                    "pricing_units": [
                        RutPricingUnitGet.model_config["json_schema_extra"]["examples"][
                            2
                        ]
                    ],
                    "is_active": True,
                },
            ]
        }
    )


class RutPricingPlanPage(NamedTuple):
    items: list[RutPricingPlanGet]
    total: PositiveInt


class PricingPlanToServiceGet(BaseModel):
    pricing_plan_id: PricingPlanId
    service_key: ServiceKey
    service_version: ServiceVersion
    created: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "service_key": "simcore/services/comp/itis/sleeper",
                    "service_version": "2.0.2",
                    "created": "2023-01-11 13:11:47.293595",
                }
            ]
        }
    )
