import logging
from collections import deque
from typing import Any, Awaitable, Deque, Optional

from aiodocker.networks import DockerNetwork
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi import Path as PathParam
from fastapi import Query, Request, Response, status
from models_library.services import ServiceOutput
from pydantic.main import BaseModel
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from servicelib.utils import logged_gather
from simcore_sdk.node_data import data_manager
from simcore_sdk.node_ports_v2.port_utils import is_file_type

from ..core.docker_compose_utils import docker_compose_restart
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.docker_utils import docker_client
from ..core.rabbitmq import RabbitMQ
from ..core.settings import DynamicSidecarSettings
from ..models.shared_store import SharedStore
from ..modules import directory_watcher, nodeports
from ..modules.mounted_fs import MountedVolumes
from ._dependencies import (
    get_application,
    get_mounted_volumes,
    get_rabbitmq,
    get_settings,
    get_shared_store,
)
from .containers import send_message

logger = logging.getLogger(__name__)


class CreateDirsRequestItem(BaseModel):
    outputs_labels: dict[str, ServiceOutput]


class PatchDirectoryWatcherItem(BaseModel):
    is_enabled: bool


class _BaseNetworkItem(BaseModel):
    network_id: str


class AttachContainerToNetworkItem(_BaseNetworkItem):
    network_aliases: list[str]


class DetachContainerFromNetworkItem(_BaseNetworkItem):
    pass


#
# HANDLERS ------------------
#
# - ANE: importing the `containers_router` router from .containers
# and generating the openapi spec, will not add the below entrypoints
# we need to create a new one in order for all the APIs to be
# detected as before
#
containers_router = APIRouter(tags=["containers"])


@containers_router.post(
    "/containers/state:restore",
    summary="Restores the state of the dynamic service",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_state(
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
    settings: DynamicSidecarSettings = Depends(get_settings),
) -> None:
    """
    When restoring the state:
    - pull inputs via nodeports
    - pull all the extra state paths
    """

    # first check if there are files (no max concurrency here, these are just quick REST calls)
    existing_files: list[bool] = await logged_gather(
        *(
            data_manager.exists(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=f"{settings.DY_SIDECAR_PROJECT_ID}",
                node_uuid=f"{settings.DY_SIDECAR_NODE_ID}",
                file_path=path,
            )
            for path in mounted_volumes.disk_state_paths()
        ),
        reraise=True,
    )

    await send_message(
        rabbitmq,
        f"Downloading state files for {existing_files}...",
    )
    await logged_gather(
        *(
            data_manager.pull(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=str(settings.DY_SIDECAR_PROJECT_ID),
                node_uuid=str(settings.DY_SIDECAR_NODE_ID),
                file_or_folder=path,
            )
            for path, exists in zip(mounted_volumes.disk_state_paths(), existing_files)
            if exists
        ),
        max_concurrency=2,  # limit amount of downloads
        reraise=True,  # this should raise if there is an issue
    )

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
    settings: DynamicSidecarSettings = Depends(get_settings),
) -> None:

    awaitables: Deque[Awaitable[Optional[Any]]] = deque()

    for state_path in mounted_volumes.disk_state_paths():
        await send_message(rabbitmq, f"Saving state for {state_path}")
        awaitables.append(
            data_manager.push(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=str(settings.DY_SIDECAR_PROJECT_ID),
                node_uuid=str(settings.DY_SIDECAR_NODE_ID),
                file_or_folder=state_path,
                r_clone_settings=settings.rclone_settings_for_nodeports,
                archive_exclude_patterns=mounted_volumes.state_exclude,
            )
        )

    await logged_gather(*awaitables, max_concurrency=2)

    await send_message(rabbitmq, "Finished state saving")


@containers_router.post(
    "/containers/ports/inputs:pull",
    summary="Pull input ports data",
    status_code=status.HTTP_200_OK,
)
async def pull_input_ports(
    port_keys: Optional[list[str]] = None,
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> int:
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling inputs for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        nodeports.PortTypeName.INPUTS,
        mounted_volumes.disk_inputs_path,
        port_keys=port_keys,
    )
    await send_message(rabbitmq, "Finished pulling inputs")
    return int(transferred_bytes)


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
    port_keys: Optional[list[str]] = None,
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> int:
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling output for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        nodeports.PortTypeName.OUTPUTS,
        mounted_volumes.disk_outputs_path,
        port_keys=port_keys,
    )
    await send_message(rabbitmq, "Finished pulling output")
    return int(transferred_bytes)


@containers_router.post(
    "/containers/ports/outputs:push",
    summary="Push output ports data",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Could not find node_uuid in the database"
        }
    },
)
async def push_output_ports(
    port_keys: Optional[list[str]] = None,
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
@cancel_on_disconnect
async def restarts_containers(
    request: Request,
    command_timeout: int = Query(
        10, description="docker-compose stop command timeout default"
    ),
    app: FastAPI = Depends(get_application),
    settings: DynamicSidecarSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
) -> None:
    """Removes the previously started service
    and returns the docker-compose output
    """
    assert request  # nosec

    if shared_store.compose_spec is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No spec for docker-compose command was found",
        )

    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    result = await docker_compose_restart(
        shared_store.compose_spec,
        settings,
        timeout=min(command_timeout, settings.DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT),
    )

    if not result.success:
        logger.warning(
            "docker-compose restart finished with errors\n%s", result.decoded_stdout
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.decoded_stdout
        )

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
    request: Request,
    item: AttachContainerToNetworkItem,
    container_id: str = PathParam(..., alias="id"),
) -> None:
    assert request  # nosec

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if item.network_id in attached_network_ids:
            logger.info(
                "Container %s already attached to network %s",
                container_id,
                item.network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=item.network_id)
        await network.connect(
            {
                "Container": container_id,
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
    item: DetachContainerFromNetworkItem,
    container_id: str = PathParam(..., alias="id"),
) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if item.network_id not in attached_network_ids:
            logger.info(
                "Container %s already detached from network %s",
                container_id,
                item.network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=item.network_id)
        await network.disconnect({"Container": container_id})
