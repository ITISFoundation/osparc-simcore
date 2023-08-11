from typing import Any

from pydantic import BaseModel

from .services import ServiceKey, ServiceVersion
from .services_resources import ServiceResourcesDict
from .wallets import WalletID


class CreateServiceMetricsAdditionalParams(BaseModel):
    wallet_id: WalletID
    wallet_name: str
    product_name: str
    simcore_user_agent: str
    user_email: str
    project_name: str
    node_name: str
    service_key: ServiceKey
    service_version: ServiceVersion
    service_resources: ServiceResourcesDict
    service_additional_metadata: dict[str, Any]
