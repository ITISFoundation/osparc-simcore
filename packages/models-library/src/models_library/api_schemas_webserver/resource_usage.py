from datetime import datetime
from decimal import Decimal

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


class PricingDetailMinimalGet(OutputSchema):
    pricing_detail_id: PricingDetailId
    unit_name: str
    cost_per_unit: Decimal
    valid_from: datetime
    simcore_default: bool


class PricingPlanGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    details: list[PricingDetailMinimalGet]
