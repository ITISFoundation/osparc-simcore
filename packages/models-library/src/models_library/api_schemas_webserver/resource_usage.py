from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

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
)
from ..services import ServiceKey, ServiceVersion
from ..users import UserID
from ..wallets import WalletID
from ._base import OutputSchema

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
    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: str
    service_resources: dict
    started_at: datetime
    stopped_at: datetime | None
    service_run_status: ServiceRunStatus


class PricingUnitGet(OutputSchema):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: dict
    current_cost_per_unit: Decimal
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


class PricingUnitAdminGet(OutputSchema):
    pricing_unit_id: PricingUnitId
    unit_name: str
    unit_extra_info: dict
    specific_info: HardwareInfo
    current_cost_per_unit: Decimal
    default: bool


class PricingPlanAdminGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitAdminGet] | None
    is_active: bool


class PricingPlanToServiceAdminGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    service_key: ServiceKey
    service_version: ServiceVersion
    created: datetime


class CreatePricingPlanBodyParams(OutputSchema):
    display_name: str
    description: str
    classification: PricingPlanClassification
    pricing_plan_key: str


class UpdatePricingPlanBodyParams(OutputSchema):
    display_name: str
    description: str
    is_active: bool


class CreatePricingUnitBodyParams(OutputSchema):
    unit_name: str
    unit_extra_info: dict
    default: bool
    specific_info: SpecificInfo
    cost_per_unit: Decimal
    comment: str


class UpdatePricingUnitBodyParams(OutputSchema):
    unit_name: str
    unit_extra_info: dict
    default: bool
    specific_info: SpecificInfo
    pricing_unit_cost_update: PricingUnitCostUpdate | None


class ConnectServiceToPricingPlanBodyParams(OutputSchema):
    service_key: ServiceKey
    service_version: ServiceVersion
