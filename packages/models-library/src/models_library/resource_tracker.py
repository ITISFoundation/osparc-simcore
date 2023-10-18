from enum import auto
from typing import Any, ClassVar, NamedTuple, TypeAlias

from pydantic import BaseModel, PositiveInt

from .utils.enums import StrAutoEnum

ServiceRunId: TypeAlias = str
PricingPlanId: TypeAlias = PositiveInt
PricingUnitId: TypeAlias = PositiveInt
PricingUnitCostId: TypeAlias = PositiveInt
CreditTransactionId: TypeAlias = PositiveInt


class ResourceTrackerServiceType(StrAutoEnum):
    COMPUTATIONAL_SERVICE = auto()
    DYNAMIC_SERVICE = auto()


class ServiceRunStatus(StrAutoEnum):
    RUNNING = auto()
    SUCCESS = auto()
    ERROR = auto()


class CreditTransactionStatus(StrAutoEnum):
    PENDING = auto()
    BILLED = auto()
    NOT_BILLED = auto()
    REQUIRES_MANUAL_REVIEW = auto()


class CreditClassification(StrAutoEnum):
    ADD_WALLET_TOP_UP = auto()  # user top up credits
    DEDUCT_SERVICE_RUN = auto()  # computational/dynamic service run costs)


class PricingPlanClassification(StrAutoEnum):
    TIER = auto()


class PricingInfo(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    pricing_unit_cost_id: PricingUnitCostId

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"pricing_plan_id": 1, "pricing_unit_id": 1, "pricing_unit_cost_id": 1}
            ]
        }


class HardwareInfo(BaseModel):
    aws_ec2_instances: list[str]

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [{"aws_ec2_instances": ["c6a.4xlarge"]}]
        }


class PricingAndHardwareInfoTuple(NamedTuple):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    current_cost_per_unit_id: PricingUnitCostId
    aws_ec2_instances: list[str]


class PricingPlanAndUnitIdsTuple(NamedTuple):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
