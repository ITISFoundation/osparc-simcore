from typing import Any, ClassVar

from pydantic import BaseModel

from .services import ServiceKey, ServiceVersion
from .services_resources import ServiceResourcesDict
from .wallets import WalletID


class CreateServiceMetricsAdditionalParams(BaseModel):
    wallet_id: WalletID | None
    wallet_name: str | None
    pricing_plan_id: int | None
    pricing_unit_id: int | None
    pricing_unit_cost_id: int | None
    product_name: str
    simcore_user_agent: str
    user_email: str
    project_name: str
    node_name: str
    service_key: ServiceKey
    service_version: ServiceVersion
    service_resources: ServiceResourcesDict
    service_additional_metadata: dict[str, Any]

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "wallet_id": 1,
                "wallet_name": "a private wallet for me",
                "pricing_plan_id": 1,
                "pricing_unit_id": 1,
                "pricing_unit_detail_id": 1,
                "product_name": "osparc",
                "simcore_user_agent": "undefined",
                "user_email": "test@test.com",
                "project_name": "_!New Study",
                "node_name": "the service of a lifetime _ *!",
                "service_key": ServiceKey("simcore/services/dynamic/test"),
                "service_version": ServiceVersion("0.0.1"),
                "service_resources": {},
                "service_additional_metadata": {},
            }
        }
