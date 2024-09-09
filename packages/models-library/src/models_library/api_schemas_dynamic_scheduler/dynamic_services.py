from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceCreate
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict


class DynamicServiceStart(DynamicServiceCreate):
    request_dns: str
    request_scheme: str
    simcore_user_agent: str
    model_config = ConfigDict()


class DynamicServiceStop(BaseModel):
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID
    simcore_user_agent: str
    save_state: bool
    model_config = ConfigDict()
