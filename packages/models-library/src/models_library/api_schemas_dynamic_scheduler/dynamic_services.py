from typing import Any, ClassVar

from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceCreate
from models_library.resource_tracker import HardwareInfo, PricingInfo
from models_library.services_resources import ServiceResourcesDictHelpers
from models_library.users import GroupID
from models_library.wallets import WalletInfo


class RPCDynamicServiceCreate(DynamicServiceCreate):
    request_dns: str
    request_scheme: str
    simcore_user_agent: str
    primary_group_id: GroupID

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "product_name": "osparc",
                "can_save": True,
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "service_key": "simcore/services/dynamic/3dviewer",
                "service_version": "2.4.5",
                "service_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "request_dns": "some.local",
                "request_scheme": "http",
                "simcore_user_agent": "",
                "service_resources": ServiceResourcesDictHelpers.Config.schema_extra[
                    "examples"
                ][0],
                "wallet_info": WalletInfo.Config.schema_extra["examples"][0],
                "pricing_info": PricingInfo.Config.schema_extra["examples"][0],
                "hardware_info": HardwareInfo.Config.schema_extra["examples"][0],
                "primary_group_id": 42,
            }
        }
