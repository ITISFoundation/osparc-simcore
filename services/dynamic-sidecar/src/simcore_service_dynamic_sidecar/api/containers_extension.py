# pylint: disable=redefined-builtin


import logging
from collections import deque
from typing import Any, Awaitable, Deque, Dict, List, Optional, Set

from aiodocker.networks import DockerNetwork
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response, status
from models_library.services import ServiceOutput
from pydantic.main import BaseModel
from servicelib.utils import logged_gather
from simcore_sdk.node_ports_common.data_items_utils import is_file_type

from ..core.dependencies import (
    get_application,
    get_mounted_volumes,
    get_rabbitmq,
    get_settings,
    get_shared_store,
)
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.docker_utils import docker_client
from ..core.rabbitmq import RabbitMQ
from ..core.settings import DynamicSidecarSettings
from ..core.shared_handlers import write_file_and_run_command
from ..models.domains.shared_store import SharedStore
from ..models.schemas.ports import PortTypeName
from ..modules import directory_watcher, nodeports
from ..modules.data_manager import pull_path_if_exists, upload_path_if_exists
from ..modules.mounted_fs import MountedVolumes
from .containers import send_message

# NOTE: importing the `containers_router` router from .containers
# and generating the openapi spec, will not add the below entrypoints
# we need to create a new one in order for all the APIs to be
# detected as before
containers_router = APIRouter(tags=["containers"])

logger = logging.getLogger(__name__)


class CreateDirsRequestItem(BaseModel):
    outputs_labels: Dict[str, ServiceOutput]


class PatchDirectoryWatcherItem(BaseModel):
    is_enabled: bool


class _BaseNetworkItem(BaseModel):
    network_id: str


class AttachContainerToNetworkItem(_BaseNetworkItem):
    network_aliases: List[str]


class DetachContainerFromNetworkItem(_BaseNetworkItem):
    pass


@containers_router.post(
    "/containers/state:restore",
    summary="Restores the state of the dynamic service",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_state(
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    """
    When restoring the state:
    - pull inputs via nodeports
    - pull all the extra state paths
    """

    awaitables: Deque[Awaitable[Optional[Any]]] = deque()

    for state_path in mounted_volumes.disk_state_paths():
        await send_message(rabbitmq, f"Downloading state for {state_path}")

        awaitables.append(pull_path_if_exists(state_path))

    await logged_gather(*awaitables)

    await send_message(rabbitmq, "Finished state downloading")


@containers_router.post(
    "/containers/state:save",
    summary="Stores the state of the dynamic service",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def save_state(
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:

    awaitables: Deque[Awaitable[Optional[Any]]] = deque()

    for state_path in mounted_volumes.disk_state_paths():
        await send_message(rabbitmq, f"Saving state for {state_path}")
        awaitables.append(
            upload_path_if_exists(state_path, mounted_volumes.state_exclude)
        )

    await logged_gather(*awaitables)

    await send_message(rabbitmq, "Finished state saving")


@containers_router.post(
    "/containers/ports/inputs:pull",
    summary="Pull input ports data",
    status_code=status.HTTP_200_OK,
)
async def pull_input_ports(
    port_keys: Optional[List[str]] = None,
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> int:
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling inputs for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        PortTypeName.INPUTS, mounted_volumes.disk_inputs_path, port_keys=port_keys
    )
    await send_message(rabbitmq, "Finished pulling inputs")
    return transferred_bytes


@containers_router.patch(
    "/containers/directory-watcher",
    summary="Enable/disable directory-watcher event propagation",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def toggle_directory_watcher(
    patch_directory_watcher_item: PatchDirectoryWatcherItem,
    app: FastAPI = Depends(get_application),
) -> None:
    if patch_directory_watcher_item.is_enabled:
        directory_watcher.enable_directory_watcher(app)
    else:
        directory_watcher.disable_directory_watcher(app)


@containers_router.post(
    "/containers/ports/outputs/dirs",
    summary=(
        "Creates the output directories declared by the docker images's labels. "
        "It is more convenient to pass the labels from director-v2, "
        "since it already has all the machinery to call into director-v0 "
        "to retrieve them."
    ),
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_output_dirs(
    request_mode: CreateDirsRequestItem,
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    outputs_path = mounted_volumes.disk_outputs_path
    for port_key, service_output in request_mode.outputs_labels.items():
        if is_file_type(service_output.property_type):
            dir_to_create = outputs_path / port_key
            dir_to_create.mkdir(parents=True, exist_ok=True)


@containers_router.post(
    "/containers/ports/outputs:pull",
    summary="Pull output ports data",
    status_code=status.HTTP_200_OK,
)
async def pull_output_ports(
    port_keys: Optional[List[str]] = None,
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> int:
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling output for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        PortTypeName.OUTPUTS, mounted_volumes.disk_outputs_path, port_keys=port_keys
    )
    await send_message(rabbitmq, "Finished pulling output")
    return transferred_bytes


@containers_router.post(
    "/containers/ports/outputs:push",
    summary="Push output ports data",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def push_output_ports(
    port_keys: Optional[List[str]] = None,
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pushing outputs for {port_keys}")
    await nodeports.upload_outputs(
        mounted_volumes.disk_outputs_path, port_keys=port_keys
    )
    await send_message(rabbitmq, "Finished pulling outputs")


@containers_router.post(
    "/containers:restart",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Container does not exist"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error while running docker-compose command"
        },
    },
)
async def restarts_containers(
    command_timeout: float = Query(
        10.0, description="docker-compose stop command timeout default"
    ),
    app: FastAPI = Depends(get_application),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
) -> None:
    """Removes the previously started service
    and returns the docker-compose output"""

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No spec for docker-compose command was found",
        )

    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    command = (
        "docker-compose --project-name {project} --file {file_path} "
        "restart --timeout {stop_and_remove_timeout}"
    )

    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=stored_compose_content,
        command=command,
        command_timeout=command_timeout,
    )
    if not finished_without_errors:
        error_message = (f"'{command}' finished with errors\n{stdout}",)
        logger.warning(error_message)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=stdout)

    for container_name in shared_store.container_names:
        await start_log_fetching(app, container_name)

    await send_message(rabbitmq, "Service was restarted please reload the UI")
    await rabbitmq.send_event_reload_iframe()


@containers_router.post(
    "/containers/{id}/networks:attach",
    summary="attach container to a network, if not already attached",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def attach_container_to_network(
    id: str, item: AttachContainerToNetworkItem
) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)
        container_inspect = await container_instance.show()

        attached_network_ids: Set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if item.network_id in attached_network_ids:
            logger.info(
                "Container %s already attached to network %s", id, item.network_id
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=item.network_id)
        await network.connect(
            {
                "Container": id,
                "EndpointConfig": {"Aliases": item.network_aliases},
            }
        )


@containers_router.post(
    "/containers/{id}/networks:detach",
    summary="detach container from a network, if not already detached",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_container_from_network(
    id: str, item: DetachContainerFromNetworkItem
) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(id)
        container_inspect = await container_instance.show()

        attached_network_ids: Set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if item.network_id not in attached_network_ids:
            logger.info(
                "Container %s already detached from network %s", id, item.network_id
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=item.network_id)
        await network.disconnect({"Container": id})
