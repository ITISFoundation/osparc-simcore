from datetime import datetime
from decimal import Decimal

from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import (
    CreditTransactionStatus,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    ResourceTrackerServiceType,
    ServiceRunId,
    ServiceRunStatus,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, NonNegativeInt


class ServiceRunCreate(BaseModel):
    product_name: ProductName
    service_run_id: ServiceRunId
    wallet_id: WalletID | None
    wallet_name: str | None
    pricing_plan_id: PricingPlanId | None
    pricing_unit_id: PricingUnitId | None
    pricing_unit_cost_id: PricingUnitCostId | None
    pricing_unit_cost: Decimal | None
    simcore_user_agent: str
    user_id: UserID
    user_email: str
    project_id: ProjectID
    project_name: str
    node_id: NodeID
    node_name: str
    parent_project_id: ProjectID
    root_parent_project_id: ProjectID
    root_parent_project_name: str
    parent_node_id: NodeID
    root_parent_node_id: NodeID
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
    service_run_status_msg: str | None


class ServiceRunDB(BaseModel):
    product_name: ProductName
    service_run_id: ServiceRunId
    wallet_id: WalletID | None
    wallet_name: str | None
    pricing_plan_id: PricingPlanId | None
    pricing_unit_id: PricingUnitId | None
    pricing_unit_cost_id: PricingUnitCostId | None
    pricing_unit_cost: Decimal | None
    user_id: UserID
    user_email: str
    project_id: ProjectID
    project_name: str
    node_id: NodeID
    node_name: str
    parent_project_id: ProjectID
    root_parent_project_id: ProjectID
    root_parent_project_name: str
    parent_node_id: NodeID
    root_parent_node_id: NodeID
    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: ResourceTrackerServiceType
    service_resources: dict
    started_at: datetime
    stopped_at: datetime | None
    service_run_status: ServiceRunStatus
    modified: datetime
    last_heartbeat_at: datetime
    service_run_status_msg: str | None
    missed_heartbeat_counter: NonNegativeInt
    model_config = ConfigDict(from_attributes=True)


class ServiceRunWithCreditsDB(ServiceRunDB):
    osparc_credits: Decimal | None = None
    transaction_status: CreditTransactionStatus | None
    project_tags: list[str]

    model_config = ConfigDict(from_attributes=True)


class OsparcCreditsAggregatedByServiceKeyDB(BaseModel):
    osparc_credits: Decimal
    service_key: ServiceKey
    running_time_in_hours: Decimal

    model_config = ConfigDict(from_attributes=True)


class ServiceRunForCheckDB(BaseModel):
    service_run_id: ServiceRunId
    last_heartbeat_at: datetime
    missed_heartbeat_counter: NonNegativeInt
    modified: datetime
    model_config = ConfigDict(from_attributes=True)
