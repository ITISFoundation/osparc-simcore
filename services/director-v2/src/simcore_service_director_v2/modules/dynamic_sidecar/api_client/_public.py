import logging
from collections import deque
from functools import cached_property
from typing import Any, Coroutine, Final

from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from models_library.projects_nodes_io import NodeID
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import AnyHttpUrl, PositiveFloat
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressCallback,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    periodic_task_result,
)
from servicelib.logging_utils import log_context, log_decorator
from servicelib.utils import logged_gather
from simcore_service_director_v2.core.settings import DynamicSidecarSettings

from ....models.schemas.dynamic_services import SchedulerData
from ....modules.dynamic_sidecar.docker_api import get_or_create_networks_ids
from ..errors import EntrypointContainerNotFoundError
from ._errors import BaseClientHTTPError, UnexpectedStatusError
from ._thin import ThinSidecarsClient

STATUS_POLL_INTERVAL: Final[PositiveFloat] = 1

logger = logging.getLogger(__name__)


async def _debug_progress_callback(
    message: ProgressMessage, percent: ProgressPercent, task_id: TaskId
) -> None:
    logger.debug("%s: %.2f %s", task_id, percent, message)


class SidecarsClient:
    """
    API client used for talking with:
        - dynamic-sidecar
        - caddy proxy
    """

    def __init__(self, app: FastAPI):
        self._app = app
        self._thin_client: ThinSidecarsClient = ThinSidecarsClient(app)

    @cached_property
    def _async_client(self) -> AsyncClient:
        return self._thin_client.client

    @cached_property
    def _dynamic_sidecar_settings(self) -> DynamicSidecarSettings:
        settings: DynamicSidecarSettings = (
            self._app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        return settings

    async def is_healthy(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, with_retry: bool = True
    ) -> bool:
        """returns True if service is UP and running else False"""
        try:
            # this request uses a very short timeout
            if with_retry:
                response = await self._thin_client.get_health(dynamic_sidecar_endpoint)
            else:
                response = await self._thin_client.get_health_no_retry(
                    dynamic_sidecar_endpoint
                )
            result: bool = response.json()["is_healthy"]
            return result
        except BaseClientHTTPError:
            return False

    async def containers_inspect(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, Any]:
        """
        returns dict containing docker inspect result form
        all dynamic-sidecar started containers
        """
        response = await self._thin_client.get_containers(
            dynamic_sidecar_endpoint, only_status=False
        )
        result: dict[str, Any] = response.json()
        return result

    @log_decorator(logger=logger)
    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, dict[str, str]]:
        try:
            response = await self._thin_client.get_containers(
                dynamic_sidecar_endpoint, only_status=True
            )
            result: dict[str, dict[str, str]] = response.json()
            return result
        except UnexpectedStatusError:
            return {}

    @log_decorator(logger=logger)
    async def disable_service_outputs_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        await self._thin_client.patch_containers_outputs_watcher(
            dynamic_sidecar_endpoint, is_enabled=False
        )

    @log_decorator(logger=logger)
    async def enable_service_outputs_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        await self._thin_client.patch_containers_outputs_watcher(
            dynamic_sidecar_endpoint, is_enabled=True
        )

    @log_decorator(logger=logger)
    async def service_outputs_create_dirs(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, outputs_labels: dict[str, Any]
    ) -> None:
        await self._thin_client.post_containers_ports_outputs_dirs(
            dynamic_sidecar_endpoint, outputs_labels=outputs_labels
        )

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
            response = await self._thin_client.get_containers_name(
                dynamic_sidecar_endpoint,
                dynamic_sidecar_network_name=dynamic_sidecar_network_name,
            )
            container_name: str = response.json()
            return container_name
        except UnexpectedStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise EntrypointContainerNotFoundError() from e
            raise e

    async def _attach_container_to_network(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        container_id: str,
        network_id: str,
        network_aliases: list[str],
    ) -> None:
        """attaches a container to a network if not already attached"""
        await self._thin_client.post_containers_networks_attach(
            dynamic_sidecar_endpoint,
            container_id=container_id,
            network_id=network_id,
            network_aliases=network_aliases,
        )

    async def _detach_container_from_network(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, container_id: str, network_id: str
    ) -> None:
        """detaches a container from a network if not already detached"""
        await self._thin_client.post_containers_networks_detach(
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
        except BaseClientHTTPError:
            # if no containers are found it is ok to skip the operations,
            # there are no containers to attach the network to
            return

        sorted_container_names = sorted(containers_status.keys())

        try:
            entrypoint_container_name = await self.get_entrypoint_container_name(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                dynamic_sidecar_network_name=dynamic_sidecar_network_name,
            )
        except EntrypointContainerNotFoundError:
            # project_network changes are propagated form the workbench before
            # the user services are started. It is safe to skip
            return

        network_names_to_ids: dict[str, str] = await get_or_create_networks_ids(
            [project_network], project_id
        )
        network_id = network_names_to_ids[project_network]

        coroutines: deque[Coroutine] = deque()

        for k, container_name in enumerate(sorted_container_names):
            # by default we attach `alias-0`, `alias-1`, etc...
            # to all containers
            aliases = [f"{network_alias}-{k}"]
            if container_name == entrypoint_container_name:
                # by definition the entrypoint container will be exposed as the `alias`
                aliases.append(network_alias)

            coroutines.append(
                self._attach_container_to_network(
                    dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                    container_id=container_name,
                    network_id=network_id,
                    network_aliases=aliases,
                )
            )

        await logged_gather(*coroutines)

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
        except BaseClientHTTPError:
            # if no containers are found it is ok to skip the operations,
            # there are no containers to detach the network from
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

    def _get_client(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> Client:
        return Client(
            app=self._app,
            async_client=self._async_client,
            base_url=dynamic_sidecar_endpoint,
        )

    async def _await_for_result(
        self,
        task_id: TaskId,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        task_timeout: PositiveFloat,
        progress_callback: ProgressCallback | None = None,
    ) -> Any | None:
        async with periodic_task_result(
            self._get_client(dynamic_sidecar_endpoint),
            task_id,
            task_timeout=task_timeout,
            progress_callback=progress_callback,
            status_poll_interval=STATUS_POLL_INTERVAL,
        ) as result:
            logger.debug("Task %s finished", task_id)
            return result

    async def create_containers(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        compose_spec: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks(
            dynamic_sidecar_endpoint, compose_spec=compose_spec
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START,
            progress_callback,
        )

    async def stop_service(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks_down(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_WAIT_FOR_SERVICE_TO_STOP,
            progress_callback,
        )

    async def restore_service_state(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        response = await self._thin_client.post_containers_tasks_state_restore(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            _debug_progress_callback,
        )

    async def save_service_state(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks_state_save(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            progress_callback,
        )

    async def pull_service_input_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: list[str] | None = None,
    ) -> int:
        response = await self._thin_client.post_containers_tasks_ports_inputs_pull(
            dynamic_sidecar_endpoint, port_keys
        )
        task_id: TaskId = response.json()

        transferred_bytes = await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            _debug_progress_callback,
        )
        return transferred_bytes or 0

    async def pull_service_output_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: list[str] | None = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks_ports_outputs_pull(
            dynamic_sidecar_endpoint, port_keys
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            _debug_progress_callback,
        )

    async def push_service_output_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks_ports_outputs_push(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            progress_callback,
        )

    async def restart_containers(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        response = await self._thin_client.post_containers_tasks_restart(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT,
            _debug_progress_callback,
        )

    async def update_volume_state(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        volume_category: VolumeCategory,
        volume_status: VolumeStatus,
    ) -> None:
        await self._thin_client.put_volumes(
            dynamic_sidecar_endpoint,
            volume_category=volume_category,
            volume_status=volume_status,
        )

    async def configure_proxy(
        self,
        proxy_endpoint: AnyHttpUrl,
        entrypoint_container_name: str,
        service_port: PortInt,
    ) -> None:
        proxy_configuration = _get_proxy_configuration(
            entrypoint_container_name, service_port
        )
        await self._thin_client.proxy_config_load(proxy_endpoint, proxy_configuration)


def _get_proxy_configuration(
    entrypoint_container_name: str, service_port: PortInt
) -> dict[str, Any]:
    return {
        # NOTE: the admin endpoint is not present any more.
        # This avoids user services from being able to access it.
        "apps": {
            "http": {
                "servers": {
                    "userservice": {
                        "listen": ["0.0.0.0:80"],
                        "routes": [
                            {
                                "handle": [
                                    {
                                        "handler": "reverse_proxy",
                                        "upstreams": [
                                            {
                                                "dial": f"{entrypoint_container_name}:{service_port}"
                                            }
                                        ],
                                    }
                                ]
                            }
                        ],
                    }
                }
            }
        },
    }


async def setup(app: FastAPI) -> None:
    with log_context(logger, logging.DEBUG, "dynamic-sidecar api client setup"):
        app.state.sidecars_api_clients = {}


async def shutdown(app: FastAPI) -> None:
    with log_context(logger, logging.DEBUG, "dynamic-sidecar api client closing..."):
        await logged_gather(
            *(
                x._thin_client.close()  # pylint: disable=protected-access
                for x in app.state.sidecars_api_clients.values()
            ),
            reraise=False,
        )


def get_sidecars_client(app: FastAPI, node_id: str | NodeID) -> SidecarsClient:
    str_node_id = f"{node_id}"

    if str_node_id not in app.state.sidecars_api_clients:
        app.state.sidecars_api_clients[str_node_id] = SidecarsClient(app)

    client: SidecarsClient = app.state.sidecars_api_clients[str_node_id]
    return client


def remove_sidecars_client(app: FastAPI, node_id: NodeID) -> None:
    app.state.sidecars_api_clients.pop(f"{node_id}", None)


async def get_dynamic_sidecar_service_health(
    app: FastAPI, scheduler_data: SchedulerData, *, with_retry: bool = True
) -> bool:
    api_client = get_sidecars_client(app, scheduler_data.node_uuid)

    # update service health
    is_healthy = await api_client.is_healthy(
        scheduler_data.endpoint, with_retry=with_retry
    )
    return is_healthy
