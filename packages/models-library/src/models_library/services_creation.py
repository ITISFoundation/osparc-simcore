from typing import Any

from pydantic import BaseModel, ConfigDict

from .services import ServiceKey, ServiceVersion
from .services_resources import ServiceResourcesDict
from .wallets import WalletID


class CreateServiceMetricsAdditionalParams(BaseModel):
    wallet_id: WalletID | None = None
    wallet_name: str | None = None
    pricing_plan_id: int | None = None
    pricing_unit_id: int | None = None
    pricing_unit_cost_id: int | None = None
    product_name: str
    simcore_user_agent: str
    user_email: str
    project_name: str
    node_name: str
    service_key: ServiceKey
    service_version: ServiceVersion
    service_resources: ServiceResourcesDict
    service_additional_metadata: dict[str, Any]
    model_config = ConfigDict()
