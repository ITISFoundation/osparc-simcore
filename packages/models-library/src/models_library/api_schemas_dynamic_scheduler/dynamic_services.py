from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceCreate
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo, PricingInfo
from models_library.services_resources import ServiceResourcesDictHelpers
from models_library.users import UserID
from models_library.wallets import WalletInfo
from pydantic import BaseModel, ConfigDict


class DynamicServiceStart(DynamicServiceCreate):
    request_dns: str
    request_scheme: str
    simcore_user_agent: str

    model_config = ConfigDict(
        json_schema_extra={
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
                "service_resources": ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                "wallet_info": WalletInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                "pricing_info": PricingInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                "hardware_info": HardwareInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
            }
        }
    )


class DynamicServiceStop(BaseModel):
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID
    simcore_user_agent: str
    save_state: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "node_id": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "simcore_user_agent": "",
                "save_state": True,
            }
        }
    )
