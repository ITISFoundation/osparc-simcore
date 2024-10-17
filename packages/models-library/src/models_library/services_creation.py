from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter

from .services_resources import ServiceResourcesDict
from .services_types import ServiceKey, ServiceVersion
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

    model_config = ConfigDict(
        json_schema_extra={
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
                "service_key": TypeAdapter(ServiceKey).validate_python(
                    "simcore/services/dynamic/test"
                ),
                "service_version": TypeAdapter(ServiceVersion).validate_python("0.0.1"),
                "service_resources": {},
                "service_additional_metadata": {},
                "pricing_unit_cost_id": None,
            }
        }
    )
