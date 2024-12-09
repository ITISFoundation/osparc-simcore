import logging
from dataclasses import dataclass, field

from aiodocker import Docker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.services import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.utils import limited_gather

from .docker_utils import get_containers_with_prefixes, remove_container_forcefully

_logger = logging.getLogger(__name__)


@dataclass
class ContainersManager(SingletonInAppStateMixin):
    app_state_name: str = "containers_manager"

    docker: Docker = field(default_factory=Docker)

    async def force_container_cleanup(self, node_id: NodeID) -> None:
        # compose all possible used container prefixes
        proxy_prefix = f"{DYNAMIC_PROXY_SERVICE_PREFIX}_{node_id}"
        dy_sidecar_prefix = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_id}"
        user_service_prefix = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}-{node_id}"

        orphan_containers = await get_containers_with_prefixes(
            self.docker, {proxy_prefix, dy_sidecar_prefix, user_service_prefix}
        )

        _logger.debug(
            "Orphan containers for node_id='%s': %s", node_id, orphan_containers
        )

        await limited_gather(
            *[
                remove_container_forcefully(self.docker, container)
                for container in orphan_containers
            ],
        )

    async def shutdown(self) -> None:
        await self.docker.close()


def get_containers_manager(app: FastAPI) -> ContainersManager:
    return ContainersManager.get_from_app_state(app)


def setup_containers_manager(app: FastAPI) -> None:
    async def _on_startup() -> None:
        ContainersManager().set_to_app_state(app)

    async def _on_shutdown() -> None:
        await ContainersManager.get_from_app_state(app).shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
