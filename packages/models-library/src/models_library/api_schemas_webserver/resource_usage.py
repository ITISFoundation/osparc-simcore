from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..resource_tracker import (
    HardwareInfo,
    PricingPlanClassification,
    PricingPlanId,
    PricingUnitCostUpdate,
    PricingUnitId,
    ServiceRunId,
    ServiceRunStatus,
    SpecificInfo,
    UnitExtraInfo,
)
from ..services import ServiceKey, ServiceVersion
from ..users import UserID
from ..wallets import WalletID
from ._base import InputSchema, OutputSchema

# Frontend API


class ServiceRunGet(
    BaseModel
):  # NOTE: this is already in use so I didnt modidy inheritance from OutputSchema
    service_run_id: ServiceRunId
    wallet_id: WalletID | None
    wallet_name: str | None
    user_id: UserID
    project_id: ProjectID
    project_name: str
    node_id: NodeID
    node_name: str
    root_parent_project_id: ProjectID
    root_parent_project_name: str
    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: str
    started_at: datetime
    stopped_at: datetime | None
    service_run_status: ServiceRunStatus


class PricingUnitGet(OutputSchema):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: UnitExtraInfo
    current_cost_per_unit: Annotated[
        Decimal, PlainSerializer(float, return_type=float, when_used="json")
    ]
    default: bool


class PricingPlanGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet]
    is_active: bool


## Admin Pricing Plan and Unit


class PricingUnitAdminGet(PricingUnitGet):
    specific_info: HardwareInfo


class PricingPlanAdminGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet] | None
    is_active: bool


class PricingPlanToServiceAdminGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    service_key: ServiceKey
    service_version: ServiceVersion
    created: datetime


class CreatePricingPlanBodyParams(InputSchema):
    display_name: str
    description: str
    classification: PricingPlanClassification
    pricing_plan_key: str

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_max_length=200,
    )


class UpdatePricingPlanBodyParams(InputSchema):
    display_name: str
    description: str
    is_active: bool

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_max_length=200,
    )


class CreatePricingUnitBodyParams(InputSchema):
    unit_name: str
    unit_extra_info: UnitExtraInfo
    default: bool
    specific_info: SpecificInfo
    cost_per_unit: Decimal
    comment: str

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_max_length=200,
    )


class UpdatePricingUnitBodyParams(InputSchema):
    unit_name: str
    unit_extra_info: UnitExtraInfo
    default: bool
    specific_info: SpecificInfo
    pricing_unit_cost_update: PricingUnitCostUpdate | None = Field(default=None)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_max_length=200,
    )


class ConnectServiceToPricingPlanBodyParams(InputSchema):
    service_key: ServiceKey
    service_version: ServiceVersion

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_max_length=200,
    )
