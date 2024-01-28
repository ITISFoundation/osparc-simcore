import logging
from datetime import datetime, timezone
from enum import auto
from typing import NamedTuple, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

from .rest_filters import Filters
from .utils.enums import StrAutoEnum

_logger = logging.getLogger(__name__)

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
    model_config = ConfigDict()


class HardwareInfo(BaseModel):
    aws_ec2_instances: list[str]
    model_config = ConfigDict()

    @field_validator("aws_ec2_instances")
    @classmethod
    @classmethod
    def warn_if_too_many_instances_are_present(cls, v: list[str]) -> list[str]:
        if len(v) > 1:
            msg = f"Only 1 entry is supported at the moment, received {v}"
            raise ValueError(msg)
        return v


class PricingAndHardwareInfoTuple(NamedTuple):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    current_cost_per_unit_id: PricingUnitCostId
    aws_ec2_instances: list[str]


class PricingPlanAndUnitIdsTuple(NamedTuple):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId


# Filtering for listing service runs/usages


class StartedAt(BaseModel):
    from_: datetime | None = Field(None, alias="from")
    until: datetime | None = Field(None)
    model_config = ConfigDict(populate_by_name=True)

    @field_validator("from_", mode="before")
    @classmethod
    @classmethod
    def parse_from_filter(cls, v):
        """Parse the filters field."""
        if v:
            if isinstance(v, datetime):
                return v
            try:
                from_ = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception as exc:
                msg = "'from' value must be provided in proper format <yyyy-mm-dd>."
                raise ValueError(msg) from exc
            return from_
        return v

    @field_validator("until", mode="before")
    @classmethod
    @classmethod
    def parse_until_filter(cls, v):
        """Parse the filters field."""
        if v:
            if isinstance(v, datetime):
                return v
            try:
                until = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception as exc:
                msg = "'until' value must be provided in proper format <yyyy-mm-dd>."
                raise ValueError(msg) from exc
            return until
        return v


class ServiceResourceUsagesFilters(Filters):
    started_at: StartedAt
