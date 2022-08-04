import logging
from collections import deque
from functools import cached_property
from typing import Any, Final, Optional

from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from pydantic import AnyHttpUrl, PositiveFloat
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressCallback,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    periodic_task_result,
)
from servicelib.utils import logged_gather
from simcore_service_director_v2.core.settings import DynamicSidecarSettings

from ....models.schemas.dynamic_services import SchedulerData
from ....modules.dynamic_sidecar.docker_api import get_or_create_networks_ids
from ....utils.logging_utils import log_decorator
from ..errors import EntrypointContainerNotFoundError
from ._errors import BaseClientHTTPError, UnexpectedStatusError
from ._thin import ThinDynamicSidecarClient

STATUS_POLL_INTERVAL: Final[PositiveFloat] = 1

logger = logging.getLogger(__name__)


async def _debug_progress_callback(
    message: ProgressMessage, percent: ProgressPercent, task_id: TaskId
) -> None:
    logger.debug("%s: %.2f %s", task_id, percent, message)


class DynamicSidecarClient:
    def __init__(self, app: FastAPI):
        self._app = app
        self._thin_client: ThinDynamicSidecarClient = ThinDynamicSidecarClient(app)

    @cached_property
    def _async_client(self) -> AsyncClient:
        return self._thin_client.client

    @cached_property
    def _dynamic_sidecar_settings(self) -> DynamicSidecarSettings:
        return self._app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR

    async def is_healthy(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> bool:
        """returns True if service is UP and running else False"""
        try:
            # this request uses a very short timeout
            response = await self._thin_client.get_health(dynamic_sidecar_endpoint)
            return response.json()["is_healthy"]
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
        return response.json()

    @log_decorator(logger=logger)
    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, dict[str, str]]:
        try:
            response = await self._thin_client.get_containers(
                dynamic_sidecar_endpoint, only_status=True
            )
            return response.json()
        except UnexpectedStatusError:
            return {}

    @log_decorator(logger=logger)
    async def service_disable_dir_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        await self._thin_client.patch_containers_directory_watcher(
            dynamic_sidecar_endpoint, is_enabled=False
        )

    @log_decorator(logger=logger)
    async def service_enable_dir_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> None:
        await self._thin_client.patch_containers_directory_watcher(
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
            return response.json()
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
        progress_callback: ProgressCallback,
        task_timeout: PositiveFloat,
    ) -> Optional[Any]:
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
        progress_callback: ProgressCallback,
    ) -> None:
        response = await self._thin_client.post_containers_tasks(
            dynamic_sidecar_endpoint, compose_spec=compose_spec
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START,
        )

    async def stop_service(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        response = await self._thin_client.post_containers_tasks_down(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_WAIT_FOR_SERVICE_TO_STOP,
        )

    async def restore_service_state(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        response = await self._thin_client.post_containers_tasks_state_restore(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
        )

    async def save_service_state(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        response = await self._thin_client.post_containers_tasks_state_save(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
        )

    async def pull_service_input_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: Optional[list[str]] = None,
    ) -> int:
        response = await self._thin_client.post_containers_tasks_ports_inputs_pull(
            dynamic_sidecar_endpoint, port_keys
        )
        task_id: TaskId = response.json()

        transferred_bytes = await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
        )
        assert transferred_bytes  # nosec
        return transferred_bytes

    async def pull_service_output_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: Optional[list[str]] = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks_ports_outputs_pull(
            dynamic_sidecar_endpoint, port_keys
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
        )

    async def push_service_output_ports(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: Optional[list[str]] = None,
    ) -> None:
        response = await self._thin_client.post_containers_tasks_ports_outputs_push(
            dynamic_sidecar_endpoint, port_keys
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
        )

    async def containers_restart(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> None:
        response = await self._thin_client.post_containers_tasks_restart(
            dynamic_sidecar_endpoint
        )
        task_id: TaskId = response.json()

        await self._await_for_result(
            task_id,
            dynamic_sidecar_endpoint,
            _debug_progress_callback,
            self._dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT,
        )


async def setup(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client setup")
    app.state.dynamic_sidecar_api_client = DynamicSidecarClient(app)


async def shutdown(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client closing...")
    client: Optional[DynamicSidecarClient]
    if client := app.state.dynamic_sidecar_api_client:
        await client._thin_client.close()  # pylint: disable=protected-access


def get_dynamic_sidecar_client(app: FastAPI) -> DynamicSidecarClient:
    assert app.state.dynamic_sidecar_api_client  # nosec
    return app.state.dynamic_sidecar_api_client


async def get_dynamic_sidecar_service_health(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    api_client = get_dynamic_sidecar_client(app)
    service_endpoint = scheduler_data.dynamic_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    scheduler_data.dynamic_sidecar.is_available = is_healthy
