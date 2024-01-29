from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceCreate
from pydantic import ConfigDict


class RPCDynamicServiceCreate(DynamicServiceCreate):
    request_dns: str
    request_scheme: str
    simcore_user_agent: str
    model_config = ConfigDict()
