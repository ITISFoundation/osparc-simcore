from datetime import datetime
from decimal import Decimal

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import (
    CreditTransactionStatus,
    ServiceRunId,
    ServiceRunStatus,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel


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
    # Cost in credits
    credit_cost: Decimal | None
    transaction_status: CreditTransactionStatus | None
