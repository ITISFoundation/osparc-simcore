from abc import ABC, abstractmethod

from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceCreate,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from servicelib.long_running_tasks.models import ProgressCallback


class SchedulerInternalsInterface(ABC):
    @abstractmethod
    async def start(self) -> None:
        """initialize scheduler internals"""

    @abstractmethod
    async def shutdown(self):
        """finalize scheduler internals"""


class SchedulerPublicInterface(ABC):
    @abstractmethod
    def toggle_observation(self, node_uuid: NodeID, *, disable: bool) -> bool:
        """
        Enables/disables the observation of the service temporarily.
        NOTE: Used by director-v2 cli.
        """

    @abstractmethod
    async def push_service_outputs(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        """
        Push service outputs.
        NOTE: Used by director-v2 cli.
        """

    @abstractmethod
    async def remove_service_containers(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        """
        Removes all started service containers.
        NOTE: Used by director-v2 cli.
        """

    @abstractmethod
    async def remove_service_sidecar_proxy_docker_networks_and_volumes(
        self, task_progress: TaskProgress, node_uuid: NodeID
    ) -> None:
        """
        Cleans up all started resources for the service.
        NOTE: Used by director-v2 cli.
        """

    @abstractmethod
    async def save_service_state(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        """
        Saves the state of the service.
        NOTE: Used by director-v2 cli.
        """

    @abstractmethod
    async def add_service(
        self,
        service: DynamicServiceCreate,
        simcore_service_labels: SimcoreServiceLabels,
        port: PortInt,
        request_dns: str,
        request_scheme: str,
        request_simcore_user_agent: str,
        *,
        can_save: bool,
    ) -> None:
        """
        Adds a new service.
        """

    @abstractmethod
    def is_service_tracked(self, node_uuid: NodeID) -> bool:
        """returns True if service is being actively observed"""

    @abstractmethod
    def list_services(
        self,
        *,
        user_id: UserID | None = None,
        project_id: ProjectID | None = None,
    ) -> list[NodeID]:
        """Returns the list of tracked service UUIDs"""

    @abstractmethod
    async def mark_service_for_removal(
        self,
        node_uuid: NodeID,
        can_save: bool | None,
        *,
        skip_observation_recreation: bool = False,
    ) -> None:
        """The service will be removed as soon as possible"""

    @abstractmethod
    async def mark_all_services_in_wallet_for_removal(
        self, wallet_id: WalletID
    ) -> None:
        """When a certain threshold is reached a message for removing all the
        services running under a certain wallet_id will be received.
        """

    @abstractmethod
    async def is_service_awaiting_manual_intervention(self, node_uuid: NodeID) -> bool:
        """
        returns True if services is waiting for manual intervention
        A service will wait for manual intervention if there was an issue while saving
        it's state or it's outputs.
        """

    @abstractmethod
    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        """Polled by the frontend for the status of the service"""

    @abstractmethod
    async def retrieve_service_inputs(
        self, node_uuid: NodeID, port_keys: list[ServicePortKey]
    ) -> RetrieveDataOutEnveloped:
        """Pulls data from input ports for the service"""

    @abstractmethod
    async def attach_project_network(
        self, node_id: NodeID, project_network: str, network_alias: DockerNetworkAlias
    ) -> None:
        """Attach project network to service"""

    @abstractmethod
    async def detach_project_network(
        self, node_id: NodeID, project_network: str
    ) -> None:
        """Detach project network from service"""

    @abstractmethod
    async def restart_containers(self, node_uuid: NodeID) -> None:
        """Restarts containers without saving or restoring the state or I/O ports"""

    @abstractmethod
    async def free_reserved_disk_space(self, node_id: NodeID) -> None:
        """Frees reserved disk space"""
