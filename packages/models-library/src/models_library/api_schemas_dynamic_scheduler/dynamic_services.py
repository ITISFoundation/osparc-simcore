from models_library.resource_tracker import HardwareInfo, PricingInfo
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from models_library.wallets import WalletInfo
from pydantic import BaseModel


class CreateDynamicService(BaseModel):
    product_name: str
    save_state: bool
    user_id: UserID
    project_id: str
    service_key: str
    service_version: str
    service_uuid: str
    request_dns: str
    request_scheme: str
    simcore_user_agent: str
    service_resources: ServiceResourcesDict
    wallet_info: WalletInfo | None
    pricing_info: PricingInfo | None
    hardware_info: HardwareInfo | None
