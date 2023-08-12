from datetime import datetime

from models_library.projects import ProjectID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import BaseModel


class ServiceRunDB(BaseModel):
    product_name: str
    service_run_id: int
    wallet_id: int
    wallet_name: str
    pricing_plan_id: int
    pricing_plan_detail: int
    simcore_user_agent: str
    user_id: UserID
    user_email: str
    project_id: ProjectID
    project_name: str
    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: str
    service_resources: dict
    service_additional_metadata: dict
    started_at: datetime
    stopped_at: datetime
    service_run_status: str
    modified: datetime
