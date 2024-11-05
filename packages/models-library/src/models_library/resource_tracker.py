import logging
from datetime import datetime, timezone
from decimal import Decimal
from enum import IntEnum, auto
from typing import NamedTuple, TypeAlias

from pydantic import (
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    field_validator,
)

from .products import ProductName
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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"pricing_plan_id": 1, "pricing_unit_id": 1, "pricing_unit_cost_id": 1}
            ]
        }
    )


class HardwareInfo(BaseModel):
    aws_ec2_instances: list[str]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"aws_ec2_instances": ["c6a.4xlarge"]},
                {"aws_ec2_instances": []},
            ]
        }
    )

    @field_validator("aws_ec2_instances")
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


## Pricing Plans


class PricingPlanCreate(BaseModel):
    product_name: ProductName
    display_name: str
    description: str
    classification: PricingPlanClassification
    pricing_plan_key: str
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_name": "osparc",
                    "display_name": "My pricing plan",
                    "description": "This is general pricing plan",
                    "classification": PricingPlanClassification.TIER,
                    "pricing_plan_key": "my-unique-pricing-plan",
                }
            ]
        }
    )


class PricingPlanUpdate(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    is_active: bool

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "display_name": "My pricing plan",
                    "description": "This is general pricing plan",
                    "is_active": True,
                }
            ]
        }
    )


## Pricing Units


class SpecificInfo(HardwareInfo):
    """Custom information that is not propagated to the frontend. For example can be used
    to store aws ec2 instance type."""


class UnitExtraInfo(BaseModel):
    """Custom information that is propagated to the frontend. Defined fields are mandatory."""

    CPU: NonNegativeInt
    RAM: ByteSize
    VRAM: ByteSize

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "CPU": 32,
                    "RAM": 64,
                    "VRAM": 0,
                    "SSD": 600,
                    "custom key": "custom value",
                }
            ]
        },
    )


class PricingUnitWithCostCreate(BaseModel):
    pricing_plan_id: PricingPlanId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    default: bool
    specific_info: SpecificInfo
    cost_per_unit: Decimal
    comment: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "unit_name": "My pricing plan",
                    "unit_extra_info": UnitExtraInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "default": True,
                    "specific_info": {"aws_ec2_instances": ["t3.medium"]},
                    "cost_per_unit": 10,
                    "comment": "This pricing unit was create by Foo",
                }
            ]
        }
    )


class PricingUnitCostUpdate(BaseModel):
    cost_per_unit: Decimal
    comment: str


class PricingUnitWithCostUpdate(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    default: bool
    specific_info: SpecificInfo
    pricing_unit_cost_update: PricingUnitCostUpdate | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pricing_plan_id": 1,
                    "pricing_unit_id": 1,
                    "unit_name": "My pricing plan",
                    "unit_extra_info": UnitExtraInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "default": True,
                    "specific_info": {"aws_ec2_instances": ["t3.medium"]},
                    "pricing_unit_cost_update": {
                        "cost_per_unit": 10,
                        "comment": "This pricing unit was updated by Foo",
                    },
                },
                {
                    "pricing_plan_id": 1,
                    "pricing_unit_id": 1,
                    "unit_name": "My pricing plan",
                    "unit_extra_info": UnitExtraInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "default": True,
                    "specific_info": {"aws_ec2_instances": ["t3.medium"]},
                    "pricing_unit_cost_update": None,
                },
            ]
        }
    )


class ServicesAggregatedUsagesType(StrAutoEnum):
    services = "services"


class ServicesAggregatedUsagesTimePeriod(IntEnum):
    ONE_DAY = 1
    ONE_WEEK = 7
    ONE_MONTH = 30
