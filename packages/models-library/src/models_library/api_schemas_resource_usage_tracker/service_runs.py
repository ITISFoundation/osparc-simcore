from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from pydantic import BaseModel, PositiveInt

from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..resource_tracker import CreditTransactionStatus, ServiceRunId, ServiceRunStatus
from ..services import ServiceKey, ServiceVersion
from ..users import UserID
from ..wallets import WalletID


class ServiceRunGet(BaseModel):
    service_run_id: ServiceRunId
    wallet_id: WalletID | None
    wallet_name: str | None
    user_id: UserID
    user_email: str
    project_id: ProjectID
    project_name: str
    project_tags: list[str]
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
    # Cost in credits
    credit_cost: Decimal | None
    transaction_status: CreditTransactionStatus | None


class ServiceRunPage(NamedTuple):
    items: list[ServiceRunGet]
    total: PositiveInt


class OsparcCreditsAggregatedByServiceGet(BaseModel):
    osparc_credits: Decimal
    service_key: ServiceKey
    running_time_in_hours: Decimal


class OsparcCreditsAggregatedUsagesPage(NamedTuple):
    items: list[OsparcCreditsAggregatedByServiceGet]
    total: PositiveInt
