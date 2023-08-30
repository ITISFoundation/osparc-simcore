from datetime import datetime
from typing import NamedTuple

from models_library.api_schemas_webserver.resource_usage import ServiceRunGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import (
    PricingDetailId,
    PricingPlanId,
    ResourceTrackerServiceType,
    ServiceRunId,
    ServiceRunStatus,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, PositiveInt


class ServiceRunCreate(BaseModel):
    product_name: ProductName
    service_run_id: ServiceRunId
    wallet_id: WalletID | None
    wallet_name: str | None
    pricing_plan_id: PricingPlanId | None
    pricing_detail_id: PricingDetailId | None
    pricing_detail_cost_per_unit: float | None
    simcore_user_agent: str
    user_id: UserID
    user_email: str
    project_id: ProjectID
    project_name: str
    node_id: NodeID
    node_name: str
    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: ResourceTrackerServiceType
    service_resources: dict
    service_additional_metadata: dict
    started_at: datetime
    service_run_status: ServiceRunStatus
    last_heartbeat_at: datetime


class ServiceRunLastHeartbeatUpdate(BaseModel):
    service_run_id: ServiceRunId
    last_heartbeat_at: datetime


class ServiceRunStoppedAtUpdate(BaseModel):
    service_run_id: ServiceRunId
    stopped_at: datetime
    service_run_status: ServiceRunStatus


class ServiceRunDB(BaseModel):
    product_name: ProductName
    service_run_id: ServiceRunId
    wallet_id: WalletID | None
    wallet_name: str | None
    pricing_plan_id: PricingPlanId | None
    pricing_detail_id: PricingDetailId | None
    pricing_detail_cost_per_unit: float | None
    user_id: UserID
    user_email: str
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

    class Config:
        orm_mode = True


class ServiceRunOnUpdateDB(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_detail_id: PricingDetailId
    started_at: datetime


class ServiceRunPage(NamedTuple):
    items: list[ServiceRunGet]
    total: PositiveInt
