import logging

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceCreate,
    RetrieveDataOutEnveloped,
    RunningDynamicServiceDetails,
)
from models_library.api_schemas_dynamic_sidecar.containers import InactivityResponse
from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.users import UserID
from servicelib.fastapi.long_running_tasks.client import ProgressCallback
from servicelib.fastapi.long_running_tasks.server import TaskProgress

from ....core.settings import DynamicServicesSchedulerSettings
from ._abc import SchedulerInternalsInterface, SchedulerPublicInterface
from ._core._scheduler import Scheduler

logger = logging.getLogger(__name__)


class DynamicSidecarsScheduler(SchedulerInternalsInterface, SchedulerPublicInterface):
    """Proxy to the current scheduler implementation"""

    def __init__(self, app: FastAPI) -> None:
        self.app: FastAPI = app
        self._scheduler = Scheduler(app=app)

    async def start(self) -> None:
        return await self._scheduler.start()

    async def shutdown(self):
        return await self._scheduler.shutdown()

    def toggle_observation(self, node_uuid: NodeID, disable: bool) -> bool:
        return self._scheduler.toggle_observation(node_uuid, disable)

    async def push_service_outputs(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        return await self._scheduler.push_service_outputs(node_uuid, progress_callback)

    async def remove_service_containers(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        return await self._scheduler.remove_service_containers(
            node_uuid, progress_callback
        )

    async def remove_service_sidecar_proxy_docker_networks_and_volumes(
        self, task_progress: TaskProgress, node_uuid: NodeID
    ) -> None:
        return await self._scheduler.remove_service_sidecar_proxy_docker_networks_and_volumes(
            task_progress, node_uuid
        )

    async def save_service_state(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        return await self._scheduler.save_service_state(node_uuid, progress_callback)

    async def add_service(
        self,
        service: DynamicServiceCreate,
        simcore_service_labels: SimcoreServiceLabels,
        port: PortInt,
        request_dns: str,
        request_scheme: str,
        request_simcore_user_agent: str,
        can_save: bool,
    ) -> None:
        return await self._scheduler.add_service(
            service,
            simcore_service_labels,
            port,
            request_dns,
            request_scheme,
            request_simcore_user_agent,
            can_save,
        )

    def is_service_tracked(self, node_uuid: NodeID) -> bool:
        return self._scheduler.is_service_tracked(node_uuid)

    def list_services(
        self, *, user_id: UserID | None = None, project_id: ProjectID | None = None
    ) -> list[NodeID]:
        return self._scheduler.list_services(user_id=user_id, project_id=project_id)

    async def mark_service_for_removal(
        self,
        node_uuid: NodeID,
        can_save: bool | None,
        skip_observation_recreation: bool = False,
    ) -> None:
        return await self._scheduler.mark_service_for_removal(
            node_uuid, can_save, skip_observation_recreation
        )

    async def is_service_awaiting_manual_intervention(self, node_uuid: NodeID) -> bool:
        return await self._scheduler.is_service_awaiting_manual_intervention(node_uuid)

    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        return await self._scheduler.get_stack_status(node_uuid)

    async def retrieve_service_inputs(
        self, node_uuid: NodeID, port_keys: list[str]
    ) -> RetrieveDataOutEnveloped:
        return await self._scheduler.retrieve_service_inputs(node_uuid, port_keys)

    async def attach_project_network(
        self, node_id: NodeID, project_network: str, network_alias: DockerNetworkAlias
    ) -> None:
        return await self._scheduler.attach_project_network(
            node_id, project_network, network_alias
        )

    async def detach_project_network(
        self, node_id: NodeID, project_network: str
    ) -> None:
        return await self._scheduler.detach_project_network(node_id, project_network)

    async def restart_containers(self, node_uuid: NodeID) -> None:
        return await self._scheduler.restart_containers(node_uuid)

    async def get_service_inactivity(self, node_id: NodeID) -> InactivityResponse:
        return await self._scheduler.get_service_inactivity(node_id)


async def setup_scheduler(app: FastAPI):
    settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    if not settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED:
        logger.warning("dynamic-sidecar scheduler will not be started!!!")
        return

    app.state.dynamic_sidecar_scheduler = scheduler = DynamicSidecarsScheduler(app)
    await scheduler.start()


async def shutdown_scheduler(app: FastAPI):
    settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    if not settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED:
        logger.warning("dynamic-sidecar scheduler not started, nothing to shutdown!!!")
        return

    scheduler: DynamicSidecarsScheduler | None = app.state.dynamic_sidecar_scheduler
    await scheduler.shutdown()


__all__: tuple[str, ...] = (
    "DynamicSidecarsScheduler",
    "setup_scheduler",
    "shutdown_scheduler",
)
