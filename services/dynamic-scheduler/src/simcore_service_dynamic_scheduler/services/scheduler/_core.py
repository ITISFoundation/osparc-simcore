from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
    GetProjectInactivityResponse,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from pydantic import NonNegativeInt


class SchedulerExpectedInterface:
    """High level interfaces that the scheduler should be able to provide"""

    async def run_dynamic_service(
        self, dynamic_service_start: DynamicServiceStart
    ) -> NodeGet | DynamicServiceGet:
        pass

    async def get_service_status(
        self, node_id: NodeID
    ) -> NodeGet | DynamicServiceGet | NodeGetIdle:
        pass

    async def stop_dynamic_service(
        self, dynamic_service_stop: DynamicServiceStop
    ) -> None:
        pass

    async def list_tracked_dynamic_services(
        self, user_id: UserID | None = None, project_id: ProjectID | None = None
    ) -> list[DynamicServiceGet]:
        pass

    async def get_project_inactivity(
        self, project_id: ProjectID, max_inactivity_seconds: NonNegativeInt
    ) -> GetProjectInactivityResponse:
        pass

    async def restart_user_services(self, node_id: NodeID) -> None:
        pass

    async def retrieve_inputs(
        self, node_id: NodeID, port_keys: list[ServicePortKey]
    ) -> RetrieveDataOutEnveloped:
        pass

    async def update_projects_networks(self, project_id: ProjectID) -> None:
        pass
