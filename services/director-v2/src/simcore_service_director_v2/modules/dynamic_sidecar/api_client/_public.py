import logging
from collections import deque
from typing import Any, Optional

from fastapi import FastAPI, status
from httpx import HTTPError
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from pydantic import AnyHttpUrl
from servicelib.utils import logged_gather

from ....models.schemas.dynamic_services import SchedulerData
from ....modules.dynamic_sidecar.docker_api import get_or_create_networks_ids
from ....utils.logging_utils import log_decorator
from ..errors import EntrypointContainerNotFoundError, NodeportsDidNotFindNodeError
from ._errors import UnexpectedStatusError, ClientTransportError
from ._thin import ThinDynamicSidecarClient

logger = logging.getLogger(__name__)


class DynamicSidecarClient:
    def __init__(self, app: FastAPI):
        self.thin_client: ThinDynamicSidecarClient = ThinDynamicSidecarClient(app)

    async def is_healthy(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> bool:
        """returns True if service is UP and running else False"""
        try:
            # this request uses a very short timeout
            response = await self.thin_client.get_health(dynamic_sidecar_endpoint)
            return response.json()["is_healthy"]
        except (HTTPError, UnexpectedStatusError, ClientTransportError):
            return False

    @log_decorator(logger=logger)
    async def containers_inspect(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, Any]:
        """
        returns dict containing docker inspect result form
        all dynamic-sidecar started containers
        """
        response = await self.thin_client.get_containers(
            dynamic_sidecar_endpoint, only_status=False
        )
        return response.json()

    @log_decorator(logger=logger)
    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, dict[str, str]]:
        try:
            response = await self.thin_client.get_containers(
                dynamic_sidecar_endpoint, only_status=True
            )
            return response.json()
        except (HTTPError, UnexpectedStatusError, ClientTransportError):
            return {}

    @log_decorator(logger=logger)
    async def start_service_creation(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, compose_spec: str
    ) -> None:
        response = await self.thin_client.post_containers(
            dynamic_sidecar_endpoint, compose_spec=compose_spec
        )
        logger.info("Spec submit result %s", response.text)

    @log_decorator(logger=logger)
    async def begin_service_destruction(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        """runs docker compose down on the started spec"""
        response = await self.thin_client.post_containers_down(dynamic_sidecar_endpoint)
        logger.info("Compose down result %s", response.text)

    @log_decorator(logger=logger)
    async def service_save_state(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        await self.thin_client.post_containers_state_save(dynamic_sidecar_endpoint)

    @log_decorator(logger=logger)
    async def service_restore_state(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        await self.thin_client.post_containers_state_restore(dynamic_sidecar_endpoint)

    @log_decorator(logger=logger)
    async def service_pull_input_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: Optional[list[str]] = None,
    ) -> int:
        port_keys = [] if port_keys is None else port_keys
        response = await self.thin_client.post_containers_ports_inputs_pull(
            dynamic_sidecar_endpoint, port_keys=port_keys
        )
        return int(response.text)

    @log_decorator(logger=logger)
    async def service_disable_dir_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        await self.thin_client.patch_containers_directory_watcher(
            dynamic_sidecar_endpoint, is_enabled=False
        )

    @log_decorator(logger=logger)
    async def service_enable_dir_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        await self.thin_client.patch_containers_directory_watcher(
            dynamic_sidecar_endpoint, is_enabled=True
        )

    @log_decorator(logger=logger)
    async def service_outputs_create_dirs(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, outputs_labels: dict[str, Any]
    ) -> None:
        await self.thin_client.post_containers_ports_outputs_dirs(
            dynamic_sidecar_endpoint, outputs_labels=outputs_labels
        )

    @log_decorator(logger=logger)
    async def service_pull_output_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: Optional[list[str]] = None,
    ) -> int:
        response = await self.thin_client.post_containers_ports_outputs_pull(
            dynamic_sidecar_endpoint, port_keys=port_keys
        )
        return int(response.text)

    @log_decorator(logger=logger)
    async def service_push_output_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: Optional[list[str]] = None,
    ) -> None:
        port_keys = [] if port_keys is None else port_keys
        try:
            await self.thin_client.post_containers_ports_outputs_push(
                dynamic_sidecar_endpoint, port_keys=port_keys
            )
        except UnexpectedStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                json_error = e.response.json()
                if json_error.get("code") == "dynamic_sidecar.nodeports.node_not_found":
                    raise NodeportsDidNotFindNodeError(
                        node_uuid=json_error["node_uuid"]
                    ) from e
            raise e

    @log_decorator(logger=logger)
    async def get_entrypoint_container_name(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, dynamic_sidecar_network_name: str
    ) -> str:
        """
        While this API raises EntrypointContainerNotFoundError
        it should be called again, because in the menwhile the containers
        might still be starting.
        """
        try:
            response = await self.thin_client.get_containers_name(
                dynamic_sidecar_endpoint,
                dynamic_sidecar_network_name=dynamic_sidecar_network_name,
            )
            return response.json()
        except UnexpectedStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise EntrypointContainerNotFoundError() from e
            raise e

    @log_decorator(logger=logger)
    async def restart_containers(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        """
        runs docker-compose stop and docker-compose start in succession
        resulting in a container restart without loosing state
        """
        await self.thin_client.post_containers_restart(dynamic_sidecar_endpoint)

    async def _attach_container_to_network(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        container_id: str,
        network_id: str,
        network_aliases: list[str],
    ) -> None:
        """attaches a container to a network if not already attached"""
        await self.thin_client.post_containers_networks_attach(
            dynamic_sidecar_endpoint,
            container_id=container_id,
            network_id=network_id,
            network_aliases=network_aliases,
        )

    async def _detach_container_from_network(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, container_id: str, network_id: str
    ) -> None:
        """detaches a container from a network if not already detached"""
        await self.thin_client.post_containers_networks_detach(
            dynamic_sidecar_endpoint, container_id=container_id, network_id=network_id
        )

    async def attach_service_containers_to_project_network(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        dynamic_sidecar_network_name: str,
        project_network: str,
        project_id: ProjectID,
        network_alias: DockerNetworkAlias,
    ) -> None:
        """All containers spawned by the dynamic-sidecar need to be attached to the project network"""
        try:
            containers_status = await self.containers_docker_status(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint
            )
        except (HTTPError, UnexpectedStatusError, ClientTransportError):
            return

        sorted_container_names = sorted(containers_status.keys())

        entrypoint_container_name = await self.get_entrypoint_container_name(
            dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
            dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        )

        network_names_to_ids: dict[str, str] = await get_or_create_networks_ids(
            [project_network], project_id
        )
        network_id = network_names_to_ids[project_network]

        tasks = deque()

        for k, container_name in enumerate(sorted_container_names):
            # by default we attach `alias-0`, `alias-1`, etc...
            # to all containers
            aliases = [f"{network_alias}-{k}"]
            if container_name == entrypoint_container_name:
                # by definition the entrypoint container will be exposed as the `alias`
                aliases.append(network_alias)

            tasks.append(
                self._attach_container_to_network(
                    dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                    container_id=container_name,
                    network_id=network_id,
                    network_aliases=aliases,
                )
            )

        await logged_gather(*tasks)

    async def detach_service_containers_from_project_network(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        project_network: str,
        project_id: ProjectID,
    ) -> None:
        # the network needs to be detached from all started containers
        try:
            containers_status = await self.containers_docker_status(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint
            )
        except (HTTPError, UnexpectedStatusError, ClientTransportError):
            return

        network_names_to_ids: dict[str, str] = await get_or_create_networks_ids(
            [project_network], project_id
        )
        network_id = network_names_to_ids[project_network]

        await logged_gather(
            *[
                self._detach_container_from_network(
                    dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                    container_id=container_name,
                    network_id=network_id,
                )
                for container_name in containers_status
            ]
        )


async def setup_api_client(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client setup")
    app.state.dynamic_sidecar_api_client = DynamicSidecarClient(app)


async def close_api_client(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client closing...")
    client: Optional[DynamicSidecarClient]
    if client := app.state.dynamic_sidecar_api_client:
        await client.thin_client.close()


def get_dynamic_sidecar_client(app: FastAPI) -> DynamicSidecarClient:
    assert app.state.dynamic_sidecar_api_client  # nosec
    return app.state.dynamic_sidecar_api_client


async def update_dynamic_sidecar_health(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    api_client = get_dynamic_sidecar_client(app)
    service_endpoint = scheduler_data.dynamic_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    scheduler_data.dynamic_sidecar.is_available = is_healthy
