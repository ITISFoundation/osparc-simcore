from datetime import datetime

from models_library.resource_tracker import (
    PricingDetailId,
    PricingPlanClassification,
    PricingPlanId,
    ServiceRunId,
    ServiceRunStatus,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel

from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..resource_tracker import ServiceRunStatus
from ..services import ServiceKey, ServiceVersion

# Frontend API


class ServiceRunGet(BaseModel):
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


class PricingDetailMinimalGet(BaseModel):
    pricing_detail_id: PricingDetailId
    unit_name: str
    cost_per_unit: float
    valid_from: datetime


class PricingPlanGet(BaseModel):
    pricing_plan_id: PricingPlanId
    name: str
    description: str
    classification: PricingPlanClassification
    created: datetime
    details: list[PricingDetailMinimalGet]
